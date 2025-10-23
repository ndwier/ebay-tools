"""eBay API integration module."""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

from config import Config

logger = logging.getLogger(__name__)


class eBayAPI:
    """Wrapper for eBay API operations."""
    
    def __init__(self):
        """Initialize eBay API connection."""
        try:
            self.api = Trading(
                domain='api.ebay.com' if Config.EBAY_ENV == 'production' else 'api.sandbox.ebay.com',
                appid=Config.EBAY_APP_ID,
                devid=Config.EBAY_DEV_ID,
                certid=Config.EBAY_CERT_ID,
                token=Config.EBAY_TOKEN,
                config_file=None
            )
            logger.info(f"Connected to eBay API ({Config.EBAY_ENV})")
        except Exception as e:
            logger.error(f"Failed to initialize eBay API: {e}")
            raise
    
    def get_active_listings(self) -> List[Dict]:
        """Get all active listings from the seller's account with pagination."""
        try:
            all_listings = []
            page_number = 1
            entries_per_page = 200
            
            while True:
                logger.info(f"Fetching page {page_number} of listings...")
                
                response = self.api.execute('GetMyeBaySelling', {
                    'ActiveList': {
                        'Include': True,
                        'Pagination': {
                            'EntriesPerPage': entries_per_page,
                            'PageNumber': page_number
                        }
                    },
                    'DetailLevel': 'ReturnAll'
                })
                
                if not response.reply.ActiveList or not hasattr(response.reply.ActiveList, 'ItemArray'):
                    break
                    
                items = response.reply.ActiveList.ItemArray.Item
                if not items:
                    break
                
                # Handle single item case (eBay returns single item as object, not array)
                if not isinstance(items, list):
                    items = [items]
                
                page_listings = []
                for item in items:
                    page_listings.append(self._parse_listing(item))
                
                all_listings.extend(page_listings)
                logger.info(f"Retrieved {len(page_listings)} listings from page {page_number}")
                
                # Check if we got fewer items than requested (last page)
                if len(page_listings) < entries_per_page:
                    break
                    
                page_number += 1
            
            logger.info(f"Retrieved {len(all_listings)} total active listings across {page_number} pages")
            return all_listings
            
        except ConnectionError as e:
            logger.error(f"eBay API error getting active listings: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting active listings: {e}")
            return []
    
    def get_sold_items(self, days: int = 30) -> List[Dict]:
        """Get sold items from the last N days."""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            response = self.api.execute('GetMyeBaySelling', {
                'SoldList': {
                    'Include': True,
                    'Pagination': {
                        'EntriesPerPage': 200
                    }
                },
                'DetailLevel': 'ReturnAll'
            })
            
            sold_items = []
            if response.reply.SoldList:
                items = response.reply.SoldList.OrderTransactionArray.OrderTransaction if hasattr(
                    response.reply.SoldList, 'OrderTransactionArray'
                ) else []
                
                for item in items:
                    sold_items.append(self._parse_sold_item(item))
            
            logger.info(f"Retrieved {len(sold_items)} sold items")
            return sold_items
            
        except ConnectionError as e:
            logger.error(f"eBay API error getting sold items: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting sold items: {e}")
            return []
    
    def end_listing(self, item_id: str, reason: str = "NotAvailable") -> bool:
        """End a listing."""
        try:
            response = self.api.execute('EndItem', {
                'ItemID': item_id,
                'EndingReason': reason
            })
            
            if response.reply.Ack in ['Success', 'Warning']:
                logger.info(f"Successfully ended item {item_id}")
                return True
            else:
                logger.error(f"Failed to end item {item_id}: {response.reply}")
                return False
                
        except ConnectionError as e:
            logger.error(f"eBay API error ending item {item_id}: {e}")
            return False

    def relist_item(self, item_id: str) -> bool:
        """Relist an ended listing."""
        try:
            response = self.api.execute('RelistItem', {
                'ItemID': item_id
            })
            
            if response.reply.Ack in ['Success', 'Warning']:
                logger.info(f"Successfully relisted item {item_id}")
                return True
            else:
                logger.error(f"Failed to relist item {item_id}: {response.reply}")
                return False
                
        except ConnectionError as e:
            logger.error(f"eBay API error relisting item {item_id}: {e}")
            return False

    def create_listing_from_template(self, original_item_id: str, new_title: str = None, new_price: float = None) -> Dict:
        """Create a new listing using an existing listing as a template."""
        try:
            # First, get the details of the original listing
            original_details = self.get_item_details(original_item_id)
            if not original_details:
                return {'success': False, 'error': 'Could not retrieve original listing details'}
            
            # Prepare the listing data
            listing_data = {
                'Title': new_title or original_details.get('title', ''),
                'Description': original_details.get('description', ''),
                'PrimaryCategory': {
                    'CategoryID': original_details.get('category_id', '')
                },
                'StartPrice': str(new_price or original_details.get('price', 0)),
                'Quantity': original_details.get('quantity', 1),
                'ListingDuration': 'GTC',  # Good 'Til Cancelled
                'ListingType': 'FixedPriceItem',
                'Location': original_details.get('location', 'United States'),
                'Country': 'US',
                'Currency': 'USD',
                'ConditionID': original_details.get('condition_id', '3000'),  # Used
                'PaymentMethods': ['PayPal'],
                'PayPalEmailAddress': 'your-paypal@email.com',  # This should be configurable
                'DispatchTimeMax': 1,
                'ShippingDetails': {
                    'ShippingType': 'Flat',
                    'ShippingServiceOptions': {
                        'ShippingServicePriority': 1,
                        'ShippingService': 'USPSMedia',
                        'ShippingServiceCost': '0.00',
                        'ShippingServiceAdditionalCost': '0.00'
                    }
                },
                'ReturnPolicy': {
                    'ReturnsAcceptedOption': 'ReturnsAccepted',
                    'RefundOption': 'MoneyBack',
                    'ReturnsWithinOption': 'Days_30',
                    'ShippingCostPaidByOption': 'Buyer'
                }
            }
            
            # Add images if available
            if original_details.get('gallery_url'):
                listing_data['PictureDetails'] = {
                    'PictureURL': [original_details['gallery_url']]
                }
            
            # Create the listing
            response = self.api.execute('AddFixedPriceItem', listing_data)
            
            if response.reply.Ack in ['Success', 'Warning']:
                new_item_id = response.reply.ItemID
                logger.info(f"Successfully created new listing {new_item_id} from template {original_item_id}")
                return {
                    'success': True,
                    'new_item_id': new_item_id,
                    'message': f'Created new listing {new_item_id}'
                }
            else:
                logger.error(f"Failed to create listing from template {original_item_id}: {response.reply}")
                return {
                    'success': False,
                    'error': f"eBay API error: {response.reply}"
                }
                
        except ConnectionError as e:
            logger.error(f"eBay API error creating listing from template {original_item_id}: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error creating listing from template {original_item_id}: {e}")
            return {'success': False, 'error': str(e)}

    def end_and_relist_item(self, item_id: str, new_title: str = None, new_price: float = None) -> Dict:
        """End a listing and create a new one with the same details."""
        try:
            logger.info(f"Starting end and relist process for item {item_id}")
            
            # Step 1: End the current listing
            if not self.end_listing(item_id):
                return {'success': False, 'error': 'Failed to end the original listing'}
            
            # Step 2: Wait a moment for eBay to process the end
            import time
            time.sleep(2)
            
            # Step 3: Create new listing from template
            result = self.create_listing_from_template(item_id, new_title, new_price)
            
            if result['success']:
                logger.info(f"Successfully completed end and relist for item {item_id} -> {result['new_item_id']}")
                return {
                    'success': True,
                    'original_item_id': item_id,
                    'new_item_id': result['new_item_id'],
                    'message': f'Ended {item_id} and created new listing {result["new_item_id"]}'
                }
            else:
                logger.error(f"Failed to create new listing after ending {item_id}: {result['error']}")
                return {
                    'success': False,
                    'error': f"Ended {item_id} but failed to create new listing: {result['error']}"
                }
                
        except Exception as e:
            logger.error(f"Unexpected error in end and relist for item {item_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def send_offer_to_buyer(self, item_id: str, buyer_id: str, offer_price: float, message: str = "") -> bool:
        """Send a price offer to a specific buyer."""
        try:
            response = self.api.execute('AddMemberMessageAAQToPartner', {
                'ItemID': item_id,
                'MemberMessage': {
                    'Body': message or f"Special offer: ${offer_price:.2f}",
                    'RecipientID': buyer_id
                }
            })
            
            if response.reply.Ack in ['Success', 'Warning']:
                logger.info(f"Successfully sent offer to buyer {buyer_id} for item {item_id}")
                return True
            else:
                logger.error(f"Failed to send offer: {response.reply}")
                return False
                
        except ConnectionError as e:
            logger.error(f"eBay API error sending offer: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending offer: {e}")
            return False
    
    def request_feedback(self, item_id: str, transaction_id: str, target_user: str) -> bool:
        """Request feedback from a buyer."""
        try:
            response = self.api.execute('CompleteSale', {
                'ItemID': item_id,
                'TransactionID': transaction_id,
                'FeedbackInfo': {
                    'CommentText': 'Thank you for your purchase! Please leave feedback.',
                    'CommentType': 'Positive',
                    'TargetUser': target_user
                }
            })
            
            if response.reply.Ack in ['Success', 'Warning']:
                logger.info(f"Successfully requested feedback for item {item_id}")
                return True
            else:
                logger.error(f"Failed to request feedback: {response.reply}")
                return False
                
        except ConnectionError as e:
            logger.error(f"eBay API error requesting feedback: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error requesting feedback: {e}")
            return False
    
    def get_item_details(self, item_id: str) -> Optional[Dict]:
        """Get detailed information about a specific item."""
        try:
            response = self.api.execute('GetItem', {
                'ItemID': item_id,
                'DetailLevel': 'ReturnAll'
            })
            
            if response.reply.Ack in ['Success', 'Warning']:
                return self._parse_listing(response.reply.Item)
            else:
                logger.error(f"Failed to get item details: {response.reply}")
                return None
                
        except ConnectionError as e:
            logger.error(f"eBay API error getting item details: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting item details: {e}")
            return None
    
    def _parse_listing(self, item) -> Dict:
        """Parse an eBay item into a standard dictionary."""
        # Debug: Log available fields
        logger.info(f"Item fields: {dir(item)}")
        
        # Try to get start time from different locations
        start_time_str = None
        end_time_str = None
        
        # First try direct fields
        if hasattr(item, 'StartTime'):
            start_time_str = getattr(item, 'StartTime', '')
            logger.info(f"StartTime field: {start_time_str}")
        elif hasattr(item, 'ListingDetails') and hasattr(item.ListingDetails, 'StartTime'):
            start_time_str = getattr(item.ListingDetails, 'StartTime', '')
            logger.info(f"StartTime from ListingDetails: {start_time_str}")
        else:
            logger.info("StartTime field: NOT_FOUND")
        
        # Try to get end time from different locations
        if hasattr(item, 'EndTime'):
            end_time_str = getattr(item, 'EndTime', '')
            logger.info(f"EndTime field: {end_time_str}")
        elif hasattr(item, 'ListingDetails') and hasattr(item.ListingDetails, 'EndTime'):
            end_time_str = getattr(item.ListingDetails, 'EndTime', '')
            logger.info(f"EndTime from ListingDetails: {end_time_str}")
        else:
            logger.info("EndTime field: NOT_FOUND")
        
        # Get the best available image URL
        gallery_url = self._get_best_image_url(item)
        
        return {
            'item_id': getattr(item, 'ItemID', ''),
            'title': getattr(item, 'Title', ''),
            'sku': getattr(item, 'SKU', ''),
            'price': float(getattr(item.SellingStatus.CurrentPrice, 'value', 0)) if hasattr(item, 'SellingStatus') else 0,
            'quantity': int(getattr(item, 'Quantity', 0)),
            'quantity_sold': int(getattr(item.SellingStatus, 'QuantitySold', 0)) if hasattr(item, 'SellingStatus') else 0,
            'listing_type': getattr(item, 'ListingType', ''),
            'start_time': self._parse_datetime(start_time_str) if start_time_str else None,
            'end_time': self._parse_datetime(end_time_str) if end_time_str else None,
            'view_count': int(getattr(item, 'HitCount', 0)),
            'watch_count': int(getattr(item, 'WatchCount', 0)),
            'condition': getattr(item.ConditionDisplayName, 'value', '') if hasattr(item, 'ConditionDisplayName') else '',
            'gallery_url': gallery_url,
        }
    
    def _get_best_image_url(self, item) -> str:
        """Get the best available image URL from eBay item data."""
        # Try different image fields in order of preference
        image_fields = [
            'GalleryURL',           # Primary gallery image
            'PictureDetails',        # Picture details object
            'PrimaryCategory',      # Sometimes has image
        ]
        
        # First try GalleryURL
        gallery_url = getattr(item, 'GalleryURL', '')
        if gallery_url and gallery_url.strip():
            logger.debug(f"Using GalleryURL: {gallery_url}")
            return gallery_url
        
        # Try PictureDetails if available
        if hasattr(item, 'PictureDetails'):
            picture_details = item.PictureDetails
            if hasattr(picture_details, 'GalleryURL'):
                gallery_url = picture_details.GalleryURL
                if gallery_url and gallery_url.strip():
                    logger.debug(f"Using PictureDetails.GalleryURL: {gallery_url}")
                    return gallery_url
            
            # Try PictureURL if available
            if hasattr(picture_details, 'PictureURL'):
                picture_urls = picture_details.PictureURL
                if picture_urls:
                    # If it's a list, take the first one
                    if isinstance(picture_urls, list) and len(picture_urls) > 0:
                        first_url = picture_urls[0]
                        if first_url and first_url.strip():
                            logger.debug(f"Using PictureDetails.PictureURL[0]: {first_url}")
                            return first_url
                    # If it's a single URL
                    elif isinstance(picture_urls, str) and picture_urls.strip():
                        logger.debug(f"Using PictureDetails.PictureURL: {picture_urls}")
                        return picture_urls
        
        # Try to construct eBay image URL from item ID as fallback
        item_id = getattr(item, 'ItemID', '')
        if item_id:
            # eBay's standard image URL format
            fallback_url = f"https://i.ebayimg.com/images/g/{item_id}/s-l500.jpg"
            logger.debug(f"Using fallback eBay image URL: {fallback_url}")
            return fallback_url
        
        logger.debug("No image URL found, returning empty string")
        return ''
    
    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Parse eBay datetime string to Python datetime object."""
        if not datetime_str:
            return None
        
        # If it's already a datetime object, return it
        if isinstance(datetime_str, datetime):
            logger.info(f"Already a datetime object: {datetime_str}")
            return datetime_str
        
        # Debug logging
        logger.info(f"Parsing datetime string: '{datetime_str}'")
        
        try:
            # eBay returns datetime in format: 2024-01-15T10:30:00.000Z
            # Remove the 'Z' and parse
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str[:-1]
            
            # Parse the datetime string
            parsed = datetime.fromisoformat(datetime_str.replace('T', ' '))
            logger.info(f"Successfully parsed datetime: {parsed}")
            return parsed
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime '{datetime_str}': {e}")
            return None
    
    def _parse_sold_item(self, order_transaction) -> Dict:
        """Parse a sold item into a standard dictionary."""
        transaction = order_transaction.Transaction
        item = transaction.Item
        
        return {
            'item_id': getattr(item, 'ItemID', ''),
            'transaction_id': getattr(transaction, 'TransactionID', ''),
            'title': getattr(item, 'Title', ''),
            'buyer_id': getattr(transaction.Buyer, 'UserID', '') if hasattr(transaction, 'Buyer') else '',
            'buyer_email': getattr(transaction.Buyer, 'Email', '') if hasattr(transaction, 'Buyer') else '',
            'sale_price': float(getattr(transaction.TransactionPrice, 'value', 0)) if hasattr(transaction, 'TransactionPrice') else 0,
            'quantity': int(getattr(transaction, 'QuantityPurchased', 0)),
            'created_date': getattr(transaction, 'CreatedDate', ''),
            'paid_time': getattr(transaction, 'PaidTime', ''),
            'shipped_time': getattr(transaction, 'ShippedTime', ''),
            'feedback_received': bool(getattr(transaction.FeedbackReceived, 'value', False)) if hasattr(transaction, 'FeedbackReceived') else False,
        }
    
    def update_listing_price(self, item_id: str, new_price: float) -> bool:
        """Update listing price."""
        try:
            response = self.api.execute('ReviseItem', {
                'Item': {
                    'ItemID': item_id,
                    'StartPrice': new_price
                }
            })
            
            logger.info(f"Updated price for item {item_id} to ${new_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating price for item {item_id}: {e}")
            return False
    
    def update_listing_quantity(self, item_id: str, new_quantity: int) -> bool:
        """Update listing quantity."""
        try:
            response = self.api.execute('ReviseItem', {
                'Item': {
                    'ItemID': item_id,
                    'Quantity': new_quantity
                }
            })
            
            logger.info(f"Updated quantity for item {item_id} to {new_quantity}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating quantity for item {item_id}: {e}")
            return False


