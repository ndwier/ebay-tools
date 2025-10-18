"""Flask application for eBay automation dashboard."""
import logging
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from config import Config
from models import db, Listing, RelistHistory, OfferSent, SoldItem, AutomationLog
from automation import AutomationEngine
from scheduler import AutomationScheduler

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
        
        # Verification token from eBay (optional but recommended)
        verification_token = request.headers.get('X-EBAY-SIGNATURE')
        if verification_token:
            logger.info(f"Received verification token: {verification_token[:10]}...")
        
        if challenge_code:
            logger.info(f"Received eBay verification challenge: {challenge_code}")
            # Return the challenge in required format
            response = {
                'challengeResponse': challenge_code
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

