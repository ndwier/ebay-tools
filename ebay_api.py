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
        """Get all active listings from the seller's account."""
        try:
            response = self.api.execute('GetMyeBaySelling', {
                'ActiveList': {
                    'Include': True,
                    'Pagination': {
                        'EntriesPerPage': 200
                    }
                },
                'DetailLevel': 'ReturnAll'
            })
            
            listings = []
            if response.reply.ActiveList:
                items = response.reply.ActiveList.ItemArray.Item if hasattr(
                    response.reply.ActiveList, 'ItemArray'
                ) else []
                
                for item in items:
                    listings.append(self._parse_listing(item))
            
            logger.info(f"Retrieved {len(listings)} active listings")
            return listings
            
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
        except Exception as e:
            logger.error(f"Unexpected error relisting item {item_id}: {e}")
            return False
    
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
        return {
            'item_id': getattr(item, 'ItemID', ''),
            'title': getattr(item, 'Title', ''),
            'sku': getattr(item, 'SKU', ''),
            'price': float(getattr(item.SellingStatus.CurrentPrice, 'value', 0)) if hasattr(item, 'SellingStatus') else 0,
            'quantity': int(getattr(item, 'Quantity', 0)),
            'quantity_sold': int(getattr(item.SellingStatus, 'QuantitySold', 0)) if hasattr(item, 'SellingStatus') else 0,
            'listing_type': getattr(item, 'ListingType', ''),
            'start_time': getattr(item, 'StartTime', ''),
            'end_time': getattr(item, 'EndTime', ''),
            'view_count': int(getattr(item, 'HitCount', 0)),
            'watch_count': int(getattr(item, 'WatchCount', 0)),
            'condition': getattr(item.ConditionDisplayName, 'value', '') if hasattr(item, 'ConditionDisplayName') else '',
            'gallery_url': getattr(item, 'GalleryURL', ''),
        }
    
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

