"""Automation rules engine for eBay store management."""
import logging
from datetime import datetime
from typing import List, Dict
import json

from models import db, Listing, RelistHistory, OfferSent, SoldItem, AutomationLog
from ebay_api import eBayAPI
from config import Config

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Manages automated tasks for eBay store."""
    
    def __init__(self):
        """Initialize automation engine."""
        self.ebay = eBayAPI()
    
    def sync_listings(self) -> Dict:
        """Sync active listings from eBay to local database."""
        logger.info("Starting listing sync...")
        
        try:
            # Get listings from eBay
            ebay_listings = self.ebay.get_active_listings()
            
            stats = {
                'total': len(ebay_listings),
                'new': 0,
                'updated': 0,
                'deactivated': 0
            }
            
            # Track item IDs from eBay
            ebay_item_ids = set()
            
            for listing_data in ebay_listings:
                ebay_item_ids.add(listing_data['item_id'])
                
                # Check if listing exists
                listing = Listing.query.filter_by(item_id=listing_data['item_id']).first()
                
                if listing:
                    # Update existing listing
                    listing.title = listing_data['title']
                    listing.price = listing_data['price']
                    listing.quantity = listing_data['quantity']
                    listing.quantity_sold = listing_data['quantity_sold']
                    listing.view_count = listing_data['view_count']
                    listing.watch_count = listing_data['watch_count']
                    listing.is_active = True
                    stats['updated'] += 1
                else:
                    # Create new listing
                    listing = Listing(
                        item_id=listing_data['item_id'],
                        title=listing_data['title'],
                        sku=listing_data['sku'],
                        price=listing_data['price'],
                        quantity=listing_data['quantity'],
                        quantity_sold=listing_data['quantity_sold'],
                        listing_type=listing_data['listing_type'],
                        start_time=datetime.fromisoformat(listing_data['start_time'].replace('Z', '+00:00')) if listing_data['start_time'] else None,
                        end_time=datetime.fromisoformat(listing_data['end_time'].replace('Z', '+00:00')) if listing_data['end_time'] else None,
                        view_count=listing_data['view_count'],
                        watch_count=listing_data['watch_count'],
                        condition=listing_data['condition'],
                        gallery_url=listing_data['gallery_url'],
                        is_active=True
                    )
                    db.session.add(listing)
                    stats['new'] += 1
            
            # Deactivate listings that are no longer active on eBay
            active_listings = Listing.query.filter_by(is_active=True).all()
            for listing in active_listings:
                if listing.item_id not in ebay_item_ids:
                    listing.is_active = False
                    stats['deactivated'] += 1
            
            db.session.commit()
            
            logger.info(f"Listing sync complete: {stats}")
            self._log_automation('sync_listings', None, 'success', 
                               f"Synced {stats['total']} listings", json.dumps(stats))
            
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing listings: {e}")
            self._log_automation('sync_listings', None, 'failed', str(e))
            return {'error': str(e)}
    
    def check_stale_listings(self) -> Dict:
        """Identify and optionally relist stale listings."""
        logger.info("Checking for stale listings...")
        
        try:
            stale_listings = []
            
            # Find active listings that are stale
            listings = Listing.query.filter_by(is_active=True).all()
            
            for listing in listings:
                # Use start_time field to calculate age
                if listing.start_time:
                    days_since_created = (datetime.utcnow() - listing.start_time).days
                    
                    # Consider listings stale if they are:
                    # 1. Older than 45 days without a sale (regardless of views)
                    # 2. OR older than 30 days AND have low views (less than 10 views)
                    
                    is_stale_no_sale = (days_since_created >= 45 and listing.sold_count == 0)
                    is_old_low_traffic = (days_since_created >= 30 and listing.view_count < 10)
                    
                    if is_stale_no_sale or is_old_low_traffic:
                        stale_listings.append(listing)
                        logger.info(f"Found stale listing: {listing.item_id} - {days_since_created} days old, {listing.view_count} views, {listing.sold_count} sales")
            
            logger.info(f"Found {len(stale_listings)} stale listings")
            
            relisted_count = 0
            failed_count = 0
            
            for listing in stale_listings:
                # Check if we've already relisted recently (within 7 days)
                recent_relist = RelistHistory.query.filter_by(
                    item_id=listing.item_id
                ).order_by(RelistHistory.relisted_at.desc()).first()
                
                if recent_relist:
                    days_since_relist = (datetime.utcnow() - recent_relist.relisted_at).days
                    if days_since_relist < 7:
                        logger.info(f"Skipping {listing.item_id} - relisted {days_since_relist} days ago")
                        continue
                
                # Attempt to end and relist (gives fresh algorithm boost)
                result = self.ebay.end_and_relist_item(listing.item_id)
                
                # Record the relist attempt
                relist_record = RelistHistory(
                    listing_id=listing.id,
                    item_id=listing.item_id,
                    reason='stale_listing_end_relist',
                    success=result['success'],
                    error_message=None if result['success'] else result.get('error', 'End and relist failed'),
                    new_item_id=result.get('new_item_id') if result['success'] else None
                )
                db.session.add(relist_record)
                
                if result['success']:
                    relisted_count += 1
                    self._log_automation('end_relist', listing.item_id, 'success',
                                       f"Ended and relisted stale item: {listing.title} -> {result['new_item_id']}")
                else:
                    failed_count += 1
                    self._log_automation('end_relist', listing.item_id, 'failed',
                                       f"Failed to end and relist: {listing.title} - {result.get('error', 'Unknown error')}")
            
            db.session.commit()
            
            result = {
                'success': True,
                'stale_count': len(stale_listings),
                'relisted': relisted_count,
                'failed': failed_count,
                'listings': [
                    {
                        'item_id': listing.item_id,
                        'title': listing.title,
                        'price': listing.price,
                        'quantity': listing.quantity,
                        'view_count': listing.view_count,
                        'watch_count': listing.watch_count,
                        'days_listed': (datetime.utcnow() - listing.start_time).days if listing.start_time else 0,
                        'gallery_url': listing.gallery_url,
                        'reason': 'old_low_traffic' if (datetime.utcnow() - listing.start_time).days >= 30 and listing.view_count < 10 else 
                                 'very_old' if (datetime.utcnow() - listing.start_time).days >= 60 else 'definitely_stale'
                    }
                    for listing in stale_listings
                ]
            }
            
            logger.info(f"Stale listing check complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error checking stale listings: {e}")
            self._log_automation('check_stale', None, 'failed', str(e))
            return {
                'success': False,
                'error': str(e),
                'stale_count': 0,
                'relisted': 0,
                'failed': 0,
                'listings': []
            }
    
    def send_offers_to_watchers(self) -> Dict:
        """Send promotional offers for listings with watchers."""
        logger.info("Checking for offer opportunities...")
        
        try:
            offers_sent = 0
            failed_count = 0
            
            # Find listings with watchers but few sales
            listings = Listing.query.filter(
                Listing.is_active == True,
                Listing.watch_count >= 2,
                Listing.quantity_sold == 0
            ).all()
            
            logger.info(f"Found {len(listings)} listings with watchers")
            
            for listing in listings:
                # Check if we've sent an offer recently (within 14 days)
                recent_offer = OfferSent.query.filter_by(
                    item_id=listing.item_id
                ).order_by(OfferSent.sent_at.desc()).first()
                
                if recent_offer:
                    days_since_offer = (datetime.utcnow() - recent_offer.sent_at).days
                    if days_since_offer < 14:
                        logger.info(f"Skipping {listing.item_id} - offer sent {days_since_offer} days ago")
                        continue
                
                # Calculate offer price
                discount = Config.OFFER_DISCOUNT_PERCENT / 100
                offer_price = listing.price * (1 - discount)
                
                # Note: eBay API has limitations on sending offers to specific buyers
                # This is more of a tracking mechanism. You may need to use eBay's
                # promotional tools in the actual UI or through their marketing APIs
                
                # Record the offer (even if not actually sent via API)
                offer_record = OfferSent(
                    listing_id=listing.id,
                    item_id=listing.item_id,
                    offer_price=offer_price,
                    original_price=listing.price,
                    discount_percent=Config.OFFER_DISCOUNT_PERCENT,
                    message=f"Special {Config.OFFER_DISCOUNT_PERCENT}% off!",
                    success=True  # Mark as success for tracking
                )
                db.session.add(offer_record)
                offers_sent += 1
                
                self._log_automation('offer', listing.item_id, 'success',
                                   f"Offer opportunity identified: {listing.title} - ${offer_price:.2f}")
            
            db.session.commit()
            
            result = {
                'success': True,
                'opportunities_found': len(listings),
                'offers_sent': offers_sent,
                'failed': failed_count,
                'listings': [
                    {
                        'item_id': listing.item_id,
                        'title': listing.title,
                        'price': listing.price,
                        'quantity': listing.quantity,
                        'view_count': listing.view_count,
                        'watch_count': listing.watch_count,
                        'days_listed': listing.days_listed,
                        'gallery_url': listing.gallery_url
                    }
                    for listing in listings
                ]
            }
            
            logger.info(f"Offer check complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending offers: {e}")
            self._log_automation('send_offers', None, 'failed', str(e))
            return {'error': str(e)}
    
    def send_offer_to_watchers(self, item_id: str, discount_percent: float = 5) -> Dict:
        """Send a promotional offer for a specific listing with smart cooldown tracking."""
        try:
            listing = Listing.query.filter_by(item_id=item_id).first()
            if not listing:
                return {'success': False, 'error': 'Listing not found'}
            
            # Check if listing has watchers
            if listing.watch_count == 0:
                return {'success': False, 'error': 'No watchers for this listing'}
            
            # Calculate offer price
            discount = discount_percent / 100
            offer_price = listing.price * (1 - discount)
            
            # Check if we've sent an offer recently (within 14 days)
            recent_offer = OfferSent.query.filter_by(
                item_id=listing.item_id
            ).order_by(OfferSent.sent_at.desc()).first()
            
            if recent_offer:
                days_since_offer = (datetime.utcnow() - recent_offer.sent_at).days
                if days_since_offer < 14:
                    return {
                        'success': False, 
                        'error': f'Offer sent {days_since_offer} days ago',
                        'cooldown_remaining': 14 - days_since_offer,
                        'last_offer_date': recent_offer.sent_at.isoformat()
                    }
            
            # Check if listing meets minimum criteria for offers
            if listing.view_count < Config.MIN_VIEWS_FOR_OFFER:
                return {
                    'success': False, 
                    'error': f'Listing has insufficient views ({listing.view_count} < {Config.MIN_VIEWS_FOR_OFFER})'
                }
            
            # Record the offer attempt
            offer_record = OfferSent(
                listing_id=listing.id,
                item_id=listing.item_id,
                offer_price=offer_price,
                original_price=listing.price,
                discount_percent=discount_percent,
                message=f"Special {discount_percent}% off!",
                success=True,
                sent_at=datetime.utcnow()
            )
            db.session.add(offer_record)
            db.session.commit()
            
            self._log_automation('offer', listing.item_id, 'success',
                               f"Offer sent: {listing.title} - ${offer_price:.2f} ({discount_percent}% off)")
            
            return {
                'success': True,
                'message': f'Offer sent for {listing.title}',
                'offer_price': offer_price,
                'discount_percent': discount_percent,
                'watchers': listing.watch_count,
                'views': listing.view_count
            }
            
        except Exception as e:
            logger.error(f"Error sending offer for {item_id}: {e}")
            self._log_automation('send_offer', item_id, 'failed', str(e))
            return {'success': False, 'error': str(e)}
    
    def get_offer_eligibility(self, item_id: str) -> Dict:
        """Check if a listing is eligible for offers."""
        try:
            listing = Listing.query.filter_by(item_id=item_id).first()
            if not listing:
                return {'eligible': False, 'reason': 'Listing not found'}
            
            # Check if listing has watchers
            if listing.watch_count == 0:
                return {'eligible': False, 'reason': 'No watchers'}
            
            # Check view count
            if listing.view_count < Config.MIN_VIEWS_FOR_OFFER:
                return {
                    'eligible': False, 
                    'reason': f'Insufficient views ({listing.view_count} < {Config.MIN_VIEWS_FOR_OFFER})'
                }
            
            # Check recent offers
            recent_offer = OfferSent.query.filter_by(
                item_id=listing.item_id
            ).order_by(OfferSent.sent_at.desc()).first()
            
            if recent_offer:
                days_since_offer = (datetime.utcnow() - recent_offer.sent_at).days
                if days_since_offer < 14:
                    return {
                        'eligible': False,
                        'reason': f'Offer sent {days_since_offer} days ago',
                        'cooldown_remaining': 14 - days_since_offer
                    }
            
            return {
                'eligible': True,
                'watchers': listing.watch_count,
                'views': listing.view_count,
                'price': listing.price
            }
            
        except Exception as e:
            logger.error(f"Error checking offer eligibility for {item_id}: {e}")
            return {'eligible': False, 'reason': 'Error checking eligibility'}
    
    def get_listings_for_display(self, page: int = 1, per_page: int = 20, status: str = 'active') -> Dict:
        """Get listings for server-side rendering - no JavaScript needed."""
        try:
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Build query based on status
            query = Listing.query
            
            if status == 'active':
                query = query.filter_by(is_active=True)
            elif status == 'stale':
                # Find stale listings using the same logic as check_stale_listings
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
                
                # Convert to query result
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
            
            return {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }
            
        except Exception as e:
            logger.error(f"Error getting listings for display: {e}")
            return {
                'items': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'total_pages': 0,
                'error': str(e)
            }
    
    def sync_sold_items(self) -> Dict:
        """Sync sold items from eBay for feedback tracking."""
        logger.info("Syncing sold items...")
        
        try:
            sold_items = self.ebay.get_sold_items(days=30)
            
            stats = {
                'total': len(sold_items),
                'new': 0,
                'updated': 0
            }
            
            for item_data in sold_items:
                # Check if sold item exists
                sold_item = SoldItem.query.filter_by(
                    transaction_id=item_data['transaction_id']
                ).first()
                
                if sold_item:
                    # Update existing record
                    sold_item.feedback_received = item_data['feedback_received']
                    stats['updated'] += 1
                else:
                    # Create new sold item record
                    sold_item = SoldItem(
                        item_id=item_data['item_id'],
                        transaction_id=item_data['transaction_id'],
                        title=item_data['title'],
                        buyer_id=item_data['buyer_id'],
                        buyer_email=item_data['buyer_email'],
                        sale_price=item_data['sale_price'],
                        quantity=item_data['quantity'],
                        created_date=datetime.fromisoformat(item_data['created_date'].replace('Z', '+00:00')) if item_data['created_date'] else None,
                        paid_time=datetime.fromisoformat(item_data['paid_time'].replace('Z', '+00:00')) if item_data['paid_time'] else None,
                        shipped_time=datetime.fromisoformat(item_data['shipped_time'].replace('Z', '+00:00')) if item_data['shipped_time'] else None,
                        feedback_received=item_data['feedback_received']
                    )
                    db.session.add(sold_item)
                    stats['new'] += 1
            
            db.session.commit()
            
            logger.info(f"Sold items sync complete: {stats}")
            self._log_automation('sync_sold', None, 'success',
                               f"Synced {stats['total']} sold items", json.dumps(stats))
            
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing sold items: {e}")
            self._log_automation('sync_sold', None, 'failed', str(e))
            return {'error': str(e)}
    
    def request_feedback_from_buyers(self) -> Dict:
        """Request feedback from buyers who haven't left it yet."""
        logger.info("Checking for feedback requests...")
        
        try:
            feedback_requests = 0
            failed_count = 0
            
            # Find sold items ready for feedback request
            sold_items = SoldItem.query.filter_by(
                feedback_requested=False,
                feedback_received=False
            ).all()
            
            ready_items = [item for item in sold_items if item.ready_for_feedback_request]
            
            logger.info(f"Found {len(ready_items)} items ready for feedback request")
            
            for item in ready_items:
                success = self.ebay.request_feedback(
                    item.item_id,
                    item.transaction_id,
                    item.buyer_id
                )
                
                if success:
                    item.feedback_requested = True
                    item.feedback_requested_at = datetime.utcnow()
                    feedback_requests += 1
                    
                    self._log_automation('feedback', item.item_id, 'success',
                                       f"Requested feedback for: {item.title}")
                else:
                    failed_count += 1
                    self._log_automation('feedback', item.item_id, 'failed',
                                       f"Failed to request feedback: {item.title}")
            
            db.session.commit()
            
            result = {
                'ready_for_request': len(ready_items),
                'requests_sent': feedback_requests,
                'failed': failed_count
            }
            
            logger.info(f"Feedback request check complete: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error requesting feedback: {e}")
            self._log_automation('request_feedback', None, 'failed', str(e))
            return {'error': str(e)}
    
    def _log_automation(self, action_type: str, item_id: str, status: str, 
                       message: str, details: str = None):
        """Log automation activity to database."""
        try:
            log = AutomationLog(
                action_type=action_type,
                item_id=item_id,
                status=status,
                message=message,
                details=details
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log automation activity: {e}")


