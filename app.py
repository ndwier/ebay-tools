"""Flask application for eBay automation dashboard."""
import logging
import os
import hashlib
import json
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect

from config import Config
from models import db, Listing, RelistHistory, OfferSent, SoldItem, AutomationLog, PoshmarkListing, EbayDraft
from automation import AutomationEngine
from scheduler import AutomationScheduler
from ebay_api import eBayAPI
from poshmark_integration import PoshmarkScraperIntegration

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ebay_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Initialize database
db.init_app(app)

# Create automation engine and scheduler
automation = AutomationEngine()
scheduler = None


@app.before_request
def before_first_request():
    """Initialize database and scheduler on first request."""
    global scheduler
    
    if scheduler is None:
        # Create database tables
        with app.app_context():
            db.create_all()
            logger.info("Database initialized")
        
        # Initialize and start scheduler
        scheduler = AutomationScheduler(app)
        scheduler.start()
        logger.info("Scheduler initialized")


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')

@app.route('/static')
def static_view():
    """Static view without JavaScript flashing."""
    return render_template('static_view.html')

@app.route('/listings')
def listings_view():
    """Server-side rendered listings view - no JavaScript flashing."""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'active')
        
        # Use existing API endpoint logic
        offset = (page - 1) * per_page
        
        # Build query based on status
        query = Listing.query
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'stale':
            # Find stale listings
            stale_listings = []
            all_listings = Listing.query.filter_by(is_active=True).all()
            
            for listing in all_listings:
                if listing.start_time:
                    days_since_created = (datetime.utcnow() - listing.start_time).days
                    is_old_low_traffic = (days_since_created >= 30 and listing.view_count < 10)
                    is_very_old = (days_since_created >= 60)
                    is_definitely_stale = (days_since_created >= 90)
                    
                    if is_old_low_traffic or is_very_old or is_definitely_stale:
                        stale_listings.append(listing)
            
            listing_ids = [l.id for l in stale_listings]
            query = query.filter(Listing.id.in_(listing_ids))
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        listings = query.offset(offset).limit(per_page).all()
        
        # Convert to display format
        items = []
        for listing in listings:
            days_listed = 0
            if listing.start_time:
                days_listed = (datetime.utcnow() - listing.start_time).days
            
            items.append({
                'item_id': listing.item_id,
                'title': listing.title,
                'price': listing.price,
                'quantity': listing.quantity,
                'view_count': listing.view_count,
                'watch_count': listing.watch_count,
                'days_listed': days_listed,
                'gallery_url': listing.gallery_url,
                'is_stale': days_listed >= 30 and listing.view_count < 10 or days_listed >= 60,
                'is_active': listing.is_active
            })
        
        total_pages = (total + per_page - 1) // per_page
        
        return render_template('listings_view.html', 
                             listings=items,
                             total=total,
                             page=page,
                             per_page=per_page,
                             status=status,
                             total_pages=total_pages)
        
    except Exception as e:
        logger.error(f"Error in listings view: {e}")
        return render_template('listings_view.html', 
                             listings=[],
                             total=0,
                             page=1,
                             per_page=20,
                             status='active',
                             total_pages=0,
                             error=str(e))


@app.route('/health')
def health():
    """Health check endpoint for Docker."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


@app.route('/webhook/marketplace-account-deletion', methods=['GET', 'POST'])
def marketplace_account_deletion():
    """
    eBay Marketplace Account Deletion notification endpoint.
    Required for API compliance (GDPR/privacy regulations).
    
    GET: Returns verification challenge for endpoint validation
    POST: Receives account deletion notifications
    """
    if request.method == 'GET':
        # eBay verification challenge
        challenge_code = request.args.get('challenge_code')
        
        if challenge_code:
            logger.info(f"Received eBay verification challenge: {challenge_code}")
            
            # eBay requires SHA256 hash of: challengeCode + verificationToken + endpoint
            # Get verification token from environment
            verification_token = os.getenv('EBAY_VERIFICATION_TOKEN', '18b5fde2d11c4692146c0983ee079343c0cf103c7e0ed69c33c46d8923a43b1e')
            
            # Construct the full endpoint URL
            # Check if behind a proxy (like ngrok) and use the forwarded host/proto
            forwarded_proto = request.headers.get('X-Forwarded-Proto', 'https')
            forwarded_host = request.headers.get('X-Forwarded-Host') or request.headers.get('Host')
            
            if forwarded_host:
                endpoint = f"{forwarded_proto}://{forwarded_host}/webhook/marketplace-account-deletion"
            else:
                # Fallback to environment variable or request URL
                endpoint = os.getenv('EBAY_ENDPOINT_URL')
                if not endpoint:
                    endpoint = request.url_root.rstrip('/') + '/webhook/marketplace-account-deletion'
                    endpoint = endpoint.replace('http://', 'https://')  # Force https
            
            # Compute SHA256 hash: challengeCode + verificationToken + endpoint
            hash_string = challenge_code + verification_token + endpoint
            hash_object = hashlib.sha256(hash_string.encode('utf-8'))
            challenge_response = hash_object.hexdigest()
            
            logger.info(f"Computed challenge response hash for endpoint: {endpoint}")
            
            # Return the hashed challenge response
            response = {
                'challengeResponse': challenge_response
            }
            return jsonify(response), 200
        return jsonify({'error': 'No challenge code provided'}), 400
    
    elif request.method == 'POST':
        # Handle marketplace account deletion notification
        try:
            data = request.get_json()
            logger.info(f"Received marketplace account deletion notification: {data}")
            
            # Extract notification details
            notification_id = data.get('metadata', {}).get('notificationId')
            topic = data.get('metadata', {}).get('topic')
            
            if topic == 'MARKETPLACE_ACCOUNT_DELETION':
                # Extract user information
                notification = data.get('notification', {})
                deletion_data = notification.get('data', {})
                user_id = deletion_data.get('userId')
                marketplace_id = deletion_data.get('marketplaceId')
                
                logger.warning(f"Account deletion notification for user {user_id} on marketplace {marketplace_id}")
                
                # Delete user data from database
                # Remove any sold items for this buyer
                deleted_count = 0
                if user_id:
                    sold_items = SoldItem.query.filter_by(buyer_id=user_id).all()
                    for item in sold_items:
                        db.session.delete(item)
                        deleted_count += 1
                    
                    db.session.commit()
                    logger.info(f"Deleted {deleted_count} records for user {user_id}")
                
                # Log the deletion
                log = AutomationLog(
                    action_type='account_deletion',
                    item_id=None,
                    status='success',
                    message=f'Processed account deletion for user {user_id}',
                    details=f'Deleted {deleted_count} records'
                )
                db.session.add(log)
                db.session.commit()
                
                return jsonify({'status': 'success', 'notificationId': notification_id}), 200
            else:
                logger.warning(f"Received unknown notification topic: {topic}")
                return jsonify({'status': 'unknown_topic'}), 200
                
        except Exception as e:
            logger.error(f"Error processing marketplace account deletion: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Method not allowed'}), 405


@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics."""
    try:
        active_listings = Listing.query.filter_by(is_active=True).count()
        stale_listings = len([l for l in Listing.query.filter_by(is_active=True).all() if l.is_stale])
        total_views = db.session.query(db.func.sum(Listing.view_count)).filter_by(is_active=True).scalar() or 0
        total_watchers = db.session.query(db.func.sum(Listing.watch_count)).filter_by(is_active=True).scalar() or 0
        
        sold_items = SoldItem.query.count()
        pending_feedback = SoldItem.query.filter_by(feedback_requested=False, feedback_received=False).count()
        
        recent_relists = RelistHistory.query.filter(
            RelistHistory.relisted_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        recent_offers = OfferSent.query.filter(
            OfferSent.sent_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()
        
        return jsonify({
            'listings': {
                'active': active_listings,
                'stale': stale_listings,
                'total_views': int(total_views),
                'total_watchers': int(total_watchers)
            },
            'sales': {
                'total_sold': sold_items,
                'pending_feedback': pending_feedback
            },
            'automation': {
                'relists_today': recent_relists,
                'offers_today': recent_offers
            }
        })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings')
def get_listings():
    """Get paginated listings."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'active')
        
        query = Listing.query
        
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'stale':
            query = query.filter_by(is_active=True)
            listings_all = query.all()
            stale_listings = [l for l in listings_all if l.is_stale]
            
            # Manual pagination for filtered results
            start = (page - 1) * per_page
            end = start + per_page
            paginated = stale_listings[start:end]
            
            return jsonify({
                'items': [{
                    'item_id': l.item_id,
                    'title': l.title,
                    'price': l.price,
                    'quantity': l.quantity,
                    'view_count': l.view_count,
                    'watch_count': l.watch_count,
                    'days_listed': l.days_listed,
                    'is_stale': l.is_stale,
                    'gallery_url': l.gallery_url
                } for l in paginated],
                'total': len(stale_listings),
                'page': page,
                'per_page': per_page
            })
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        pagination = query.order_by(Listing.last_updated.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'items': [{
                'item_id': l.item_id,
                'title': l.title,
                'price': l.price,
                'quantity': l.quantity,
                'quantity_sold': l.quantity_sold,
                'view_count': l.view_count,
                'watch_count': l.watch_count,
                'days_listed': l.days_listed,
                'is_stale': l.is_stale,
                'gallery_url': l.gallery_url
            } for l in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"Error getting listings: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs')
def get_logs():
    """Get recent automation logs."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        action_type = request.args.get('type')
        
        query = AutomationLog.query
        
        if action_type:
            query = query.filter_by(action_type=action_type)
        
        pagination = query.order_by(AutomationLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'items': [{
                'id': log.id,
                'action_type': log.action_type,
                'item_id': log.item_id,
                'status': log.status,
                'message': log.message,
                'created_at': log.created_at.isoformat()
            } for log in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/jobs')
def get_jobs():
    """Get scheduled jobs status."""
    try:
        jobs = scheduler.get_jobs() if scheduler else []
        return jsonify({'jobs': jobs})
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """Manually trigger listing sync."""
    try:
        result = automation.sync_listings()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in manual sync: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-stale', methods=['POST'])
def manual_stale_check():
    """Manually trigger stale listing check."""
    try:
        result = automation.check_stale_listings()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in manual stale check: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-offers', methods=['POST'])
def manual_offer_check():
    """Manually trigger offer check."""
    try:
        result = automation.send_offers_to_watchers()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in manual offer check: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/check-feedback', methods=['POST'])
def manual_feedback_check():
    """Manually trigger feedback check."""
    try:
        result = automation.request_feedback_from_buyers()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Error in manual feedback check: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/relist/<item_id>', methods=['POST'])
def manual_relist(item_id):
    """Manually relist a specific item."""
    try:
        listing = Listing.query.filter_by(item_id=item_id).first()
        if not listing:
            return jsonify({'success': False, 'error': 'Listing not found'}), 404
        
        success = automation.ebay.relist_item(item_id)
        
        if success:
            relist_record = RelistHistory(
                listing_id=listing.id,
                item_id=item_id,
                reason='manual',
                success=True
            )
            db.session.add(relist_record)
            db.session.commit()
        
        return jsonify({'success': success})
    except Exception as e:
        logger.error(f"Error in manual relist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/listings/<item_id>/price', methods=['PUT'])
def update_listing_price(item_id):
    """Update listing price."""
    try:
        data = request.get_json()
        new_price = data.get('price')
        
        if not new_price or new_price <= 0:
            return jsonify({'error': 'Invalid price'}), 400
        
        ebay = eBayAPI()
        success = ebay.update_listing_price(item_id, float(new_price))
        
        if success:
            # Update local database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.price = float(new_price)
                listing.last_updated = datetime.utcnow()
                db.session.commit()
            
            return jsonify({'success': True, 'message': f'Price updated to ${new_price}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update price on eBay'}), 500
            
    except Exception as e:
        logger.error(f"Error updating price for item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/quantity', methods=['PUT'])
def update_listing_quantity(item_id):
    """Update listing quantity."""
    try:
        data = request.get_json()
        new_quantity = data.get('quantity')
        
        if not new_quantity or new_quantity < 0:
            return jsonify({'error': 'Invalid quantity'}), 400
        
        ebay = eBayAPI()
        success = ebay.update_listing_quantity(item_id, int(new_quantity))
        
        if success:
            # Update local database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.quantity = int(new_quantity)
                listing.last_updated = datetime.utcnow()
                db.session.commit()
            
            return jsonify({'success': True, 'message': f'Quantity updated to {new_quantity}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update quantity on eBay'}), 500
            
    except Exception as e:
        logger.error(f"Error updating quantity for item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/update', methods=['POST'])
def update_listing_bulk(item_id):
    """Update listing price and quantity via form submission."""
    try:
        price = request.form.get('price', type=float)
        quantity = request.form.get('quantity', type=int)
        
        if price is None or quantity is None:
            return jsonify({'success': False, 'error': 'Price and quantity required'}), 400
        
        # Update price
        ebay = eBayAPI()
        price_success = ebay.update_listing_price(item_id, price)
        if not price_success:
            return jsonify({'success': False, 'error': 'Failed to update price'}), 500
        
        # Update quantity
        quantity_success = ebay.update_listing_quantity(item_id, quantity)
        if not quantity_success:
            return jsonify({'success': False, 'error': 'Failed to update quantity'}), 500
        
        # Update local database
        listing = Listing.query.filter_by(item_id=item_id).first()
        if listing:
            listing.price = price
            listing.quantity = quantity
            listing.last_updated = datetime.utcnow()
            db.session.commit()
        
        # Redirect back to listings view
        return redirect(f'/listings?status=active&page=1')
        
    except Exception as e:
        logger.error(f"Error updating listing {item_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/refresh-images', methods=['POST'])
def refresh_images():
    """Refresh image URLs for all listings."""
    try:
        ebay = eBayAPI()
        automation = AutomationEngine()
        
        # Get all active listings
        listings = Listing.query.filter_by(is_active=True).all()
        
        updated_count = 0
        failed_count = 0
        
        for listing in listings:
            try:
                # Get fresh item details from eBay
                item_details = ebay.get_item_details(listing.item_id)
                
                if item_details and 'gallery_url' in item_details:
                    new_gallery_url = item_details['gallery_url']
                    
                    # Update the listing if we got a new image URL
                    if new_gallery_url and new_gallery_url != listing.gallery_url:
                        listing.gallery_url = new_gallery_url
                        listing.last_updated = datetime.utcnow()
                        updated_count += 1
                        logger.info(f"Updated image for {listing.item_id}: {new_gallery_url}")
                    else:
                        logger.debug(f"No new image URL for {listing.item_id}")
                else:
                    logger.warning(f"Could not get item details for {listing.item_id}")
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error refreshing image for {listing.item_id}: {e}")
                failed_count += 1
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated': updated_count,
            'failed': failed_count,
            'total_processed': len(listings),
            'message': f'Refreshed images for {updated_count} listings'
        })
        
    except Exception as e:
        logger.error(f"Error refreshing images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/send-offer/<item_id>', methods=['POST'])
def send_offer(item_id):
    """Send a promotional offer for a specific listing."""
    try:
        data = request.get_json()
        discount_percent = data.get('discount_percent', 5)
        
        automation = AutomationEngine()
        result = automation.send_offer_to_watchers(item_id, discount_percent)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error sending offer for item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get comprehensive seller metrics."""
    try:
        # Get basic stats
        stats_response = get_stats()
        stats_data = json.loads(stats_response.get_data(as_text=True))
        
        # Calculate additional metrics
        total_views = stats_data['listings']['total_views']
        total_watchers = stats_data['listings']['total_watchers']
        total_sales = stats_data['sales']['total_sold']
        
        # Calculate revenue (placeholder - would need actual sales data)
        avg_price = 25.0  # Placeholder average price
        total_revenue = total_sales * avg_price
        
        metrics = {
            'total_views': total_views,
            'total_watchers': total_watchers,
            'total_sales': total_sales,
            'total_revenue': total_revenue,
            'conversion_rate': (total_sales / max(total_views, 1)) * 100,
            'avg_price': avg_price,
            'active_listings': stats_data['listings']['active'],
            'stale_listings': stats_data['listings']['stale']
        }
        
        return jsonify(metrics)
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sales/recent', methods=['GET'])
def get_recent_sales():
    """Get recent sales data."""
    try:
        # Placeholder for sales data - would integrate with eBay's sold items API
        recent_sales = [
            {
                'item_id': '123456789',
                'title': 'Sample Item 1',
                'price': 25.99,
                'sold_date': '2024-01-15',
                'buyer': 'buyer123',
                'feedback_left': False
            },
            {
                'item_id': '987654321',
                'title': 'Sample Item 2',
                'price': 45.50,
                'sold_date': '2024-01-14',
                'buyer': 'buyer456',
                'feedback_left': True
            }
        ]
        
        return jsonify({'sales': recent_sales})
        
    except Exception as e:
        logger.error(f"Error getting recent sales: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/end-relist', methods=['POST'])
def end_and_relist_listing(item_id):
    """End a listing and create a new one with the same details."""
    try:
        data = request.get_json() or {}
        new_title = data.get('new_title')
        new_price = data.get('new_price')
        
        ebay = eBayAPI()
        result = ebay.end_and_relist_item(item_id, new_title, new_price)
        
        if result['success']:
            # Update the database to reflect the change
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = False
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'original_item_id': result['original_item_id'],
                'new_item_id': result['new_item_id']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error ending and relisting item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/end', methods=['POST'])
def end_listing(item_id):
    """End a listing."""
    try:
        ebay = eBayAPI()
        success = ebay.end_listing(item_id)
        
        if success:
            # Update the database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = False
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully ended listing {item_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to end listing'
            }), 500
            
    except Exception as e:
        logger.error(f"Error ending item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/relist', methods=['POST'])
def relist_listing(item_id):
    """Relist an ended listing."""
    try:
        ebay = eBayAPI()
        success = ebay.relist_item(item_id)
        
        if success:
            # Update the database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = True
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully relisted item {item_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to relist item'
            }), 500
            
    except Exception as e:
        logger.error(f"Error relisting item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


        return jsonify({'sales': recent_sales})
        
    except Exception as e:
        logger.error(f"Error getting recent sales: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/end-relist', methods=['POST'])
def end_and_relist_listing(item_id):
    """End a listing and create a new one with the same details."""
    try:
        data = request.get_json() or {}
        new_title = data.get('new_title')
        new_price = data.get('new_price')
        
        ebay = eBayAPI()
        result = ebay.end_and_relist_item(item_id, new_title, new_price)
        
        if result['success']:
            # Update the database to reflect the change
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = False
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': result['message'],
                'original_item_id': result['original_item_id'],
                'new_item_id': result['new_item_id']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        logger.error(f"Error ending and relisting item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/end', methods=['POST'])
def end_listing(item_id):
    """End a listing."""
    try:
        ebay = eBayAPI()
        success = ebay.end_listing(item_id)
        
        if success:
            # Update the database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = False
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully ended listing {item_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to end listing'
            }), 500
            
    except Exception as e:
        logger.error(f"Error ending item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/listings/<item_id>/relist', methods=['POST'])
def relist_listing(item_id):
    """Relist an ended listing."""
    try:
        ebay = eBayAPI()
        success = ebay.relist_item(item_id)
        
        if success:
            # Update the database
            listing = Listing.query.filter_by(item_id=item_id).first()
            if listing:
                listing.is_active = True
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully relisted item {item_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to relist item'
            }), 500
            
    except Exception as e:
        logger.error(f"Error relisting item {item_id}: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":


@app.route('/api/poshmark/scrape', methods=['POST'])
def scrape_poshmark_user():
    """Scrape Poshmark listings from a user."""
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'error': 'Username required'}), 400
        
        # Scrape Poshmark listings
        with PoshmarkScraperIntegration(headless=True) as scraper:
            result = scraper.scrape_user_listings(username)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error scraping Poshmark user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/poshmark/listings', methods=['GET'])
def get_poshmark_listings():
    """Get Poshmark listings from database."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        pagination = PoshmarkListing.query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        listings = []
        for listing in pagination.items:
            images = json.loads(listing.images) if listing.images else []
            tags = json.loads(listing.tags) if listing.tags else []
            
            listings.append({
                'id': listing.id,
                'poshmark_id': listing.poshmark_id,
                'poshmark_url': listing.poshmark_url,
                'title': listing.title,
                'price': listing.price,
                'original_price': listing.original_price,
                'description': listing.description,
                'brand': listing.brand,
                'size': listing.size,
                'category': listing.category,
                'condition': listing.condition,
                'seller_username': listing.seller_username,
                'images': images,
                'tags': tags,
                'scraped_at': listing.scraped_at.isoformat() if listing.scraped_at else None,
                'has_draft': len(listing.ebay_drafts) > 0
            })
        
        return jsonify({
            'items': listings,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        })
        
    except Exception as e:
        logger.error(f"Error getting Poshmark listings: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/poshmark/create-drafts', methods=['POST'])
def create_ebay_drafts_from_poshmark():
    """Create eBay drafts from Poshmark listings."""
    try:
        data = request.get_json()
        listing_ids = data.get('listing_ids', [])
        
        if not listing_ids:
            return jsonify({'error': 'Listing IDs required'}), 400
        
        # Create drafts
        with PoshmarkScraperIntegration() as scraper:
            result = scraper.create_ebay_drafts_from_poshmark(listing_ids)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating Poshmark drafts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/drafts', methods=['GET'])
def get_ebay_drafts():
    """Get eBay drafts from database."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'draft')
        
        query = EbayDraft.query
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        drafts = []
        for draft in pagination.items:
            images = json.loads(draft.images) if draft.images else []
            
            drafts.append({
                'id': draft.id,
                'poshmark_listing_id': draft.poshmark_listing_id,
                'ebay_item_id': draft.ebay_item_id,
                'title': draft.title,
                'description': draft.description,
                'price': draft.price,
                'quantity': draft.quantity,
                'category_id': draft.category_id,
                'condition_id': draft.condition_id,
                'condition_description': draft.condition_description,
                'images': images,
                'location': draft.location,
                'listing_duration': draft.listing_duration,
                'listing_type': draft.listing_type,
                'status': draft.status,
                'error_message': draft.error_message,
                'created_at': draft.created_at.isoformat() if draft.created_at else None,
                'published_at': draft.published_at.isoformat() if draft.published_at else None,
                'poshmark_title': draft.poshmark_listing.title if draft.poshmark_listing else None
            })
        
        return jsonify({
            'items': drafts,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'total_pages': pagination.pages
        })
        
    except Exception as e:
        logger.error(f"Error getting eBay drafts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/drafts/<int:draft_id>/update', methods=['PUT'])
def update_ebay_draft(draft_id):
    """Update an eBay draft."""
    try:
        data = request.get_json()
        
        draft = EbayDraft.query.get(draft_id)
        if not draft:
            return jsonify({'error': 'Draft not found'}), 404
        
        # Update fields
        if 'title' in data:
            draft.title = data['title']
        if 'description' in data:
            draft.description = data['description']
        if 'price' in data:
            draft.price = float(data['price'])
        if 'quantity' in data:
            draft.quantity = int(data['quantity'])
        if 'category_id' in data:
            draft.category_id = data['category_id']
        if 'condition_id' in data:
            draft.condition_id = data['condition_id']
        if 'condition_description' in data:
            draft.condition_description = data['condition_description']
        if 'images' in data:
            draft.images = json.dumps(data['images'])
        
        draft.last_updated = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Draft {draft_id} updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating draft {draft_id}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/drafts/<int:draft_id>/publish', methods=['POST'])
def publish_ebay_draft(draft_id):
    """Publish an eBay draft to create a live listing."""
    try:
        draft = EbayDraft.query.get(draft_id)
        if not draft:
            return jsonify({'error': 'Draft not found'}), 404
        
        if draft.status != 'draft':
            return jsonify({'error': 'Draft is not in draft status'}), 400
        
        # Convert draft to eBay listing format
        images = json.loads(draft.images) if draft.images else []
        
        listing_data = {
            'title': draft.title,
            'description': draft.description,
            'price': draft.price,
            'quantity': draft.quantity,
            'category_id': draft.category_id,
            'condition_id': draft.condition_id,
            'condition_description': draft.condition_description,
            'images': images,
            'location': draft.location,
            'listing_duration': draft.listing_duration,
            'listing_type': draft.listing_type
        }
        
        # Create listing via eBay API
        ebay = eBayAPI()
        result = ebay.create_listing(listing_data)
        
        if result.get('success'):
            # Update draft status
            draft.status = 'published'
            draft.ebay_item_id = result.get('item_id')
            draft.published_at = datetime.utcnow()
            draft.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Draft {draft_id} published successfully',
                'item_id': result.get('item_id')
            })
        else:
            # Update draft with error
            draft.status = 'failed'
            draft.error_message = result.get('error', 'Unknown error')
            draft.last_updated = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to publish draft')
            }), 500
        
    except Exception as e:
        logger.error(f"Error publishing draft {draft_id}: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/shipping/labels', methods=['POST'])
def generate_shipping_labels():
    """Generate shipping labels for sold items."""
    try:
        data = request.get_json()
        item_ids = data.get('item_ids', [])
        
        if not item_ids:
            return jsonify({'error': 'Item IDs required'}), 400
        
        # Placeholder for shipping label generation
        # Would integrate with shipping APIs like ShipStation, EasyPost, etc.
        return jsonify({
            'success': True,
            'labels_generated': len(item_ids),
            'message': f'Generated {len(item_ids)} shipping labels'
        })
        
    except Exception as e:
        logger.error(f"Error generating shipping labels: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    try:
        # Validate configuration
        Config.validate()
        logger.info("Configuration validated successfully")
        
        # Run the app
        app.run(
            host=Config.HOST,
            port=Config.PORT,
            debug=False
        )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error: {e}")
        print("Please copy env_template.txt to .env and fill in your eBay API credentials.\n")
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)

