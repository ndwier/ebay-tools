"""Database models for eBay automation."""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Listing(db.Model):
    """Track eBay listings and their metrics."""
    
    __tablename__ = 'listings'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(100))
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    quantity_sold = db.Column(db.Integer, default=0)
    listing_type = db.Column(db.String(50))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    view_count = db.Column(db.Integer, default=0)
    watch_count = db.Column(db.Integer, default=0)
    condition = db.Column(db.String(50))
    gallery_url = db.Column(db.String(500))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    relist_history = db.relationship('RelistHistory', backref='listing', lazy=True, cascade='all, delete-orphan')
    offers = db.relationship('OfferSent', backref='listing', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Listing {self.item_id}: {self.title}>'
    
    @property
    def days_listed(self):
        """Calculate how many days the listing has been active."""
        if self.start_time:
            return (datetime.utcnow() - self.start_time).days
        return 0
    
    @property
    def is_stale(self):
        """Check if listing is considered stale based on configuration."""
        from config import Config
        return self.days_listed >= Config.STALE_LISTING_DAYS


class RelistHistory(db.Model):
    """Track when items are relisted."""
    
    __tablename__ = 'relist_history'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    item_id = db.Column(db.String(50), nullable=False, index=True)
    new_item_id = db.Column(db.String(50), nullable=True, index=True)  # For end and relist operations
    relisted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(100))
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<RelistHistory {self.item_id} -> {self.new_item_id} at {self.relisted_at}>'


class OfferSent(db.Model):
    """Track offers sent to buyers."""
    
    __tablename__ = 'offers_sent'
    
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    item_id = db.Column(db.String(50), nullable=False, index=True)
    buyer_id = db.Column(db.String(100))
    offer_price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float)
    discount_percent = db.Column(db.Float)
    message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    success = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<OfferSent {self.item_id} - ${self.offer_price}>'


class SoldItem(db.Model):
    """Track sold items for feedback management."""
    
    __tablename__ = 'sold_items'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.String(50), nullable=False, index=True)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200))
    buyer_id = db.Column(db.String(100), nullable=False)
    buyer_email = db.Column(db.String(200))
    sale_price = db.Column(db.Float)
    quantity = db.Column(db.Integer)
    created_date = db.Column(db.DateTime)
    paid_time = db.Column(db.DateTime)
    shipped_time = db.Column(db.DateTime)
    feedback_received = db.Column(db.Boolean, default=False)
    feedback_requested = db.Column(db.Boolean, default=False)
    feedback_requested_at = db.Column(db.DateTime)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SoldItem {self.item_id} to {self.buyer_id}>'
    
    @property
    def days_since_sale(self):
        """Calculate days since the item was sold."""
        if self.created_date:
            return (datetime.utcnow() - self.created_date).days
        return 0
    
    @property
    def ready_for_feedback_request(self):
        """Check if it's time to request feedback."""
        from config import Config
        return (
            not self.feedback_requested and
            not self.feedback_received and
            self.shipped_time and
            self.days_since_sale >= Config.FEEDBACK_REQUEST_DAYS
        )


class AutomationLog(db.Model):
    """Log all automation activities."""
    
    __tablename__ = 'automation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)  # 'relist', 'offer', 'feedback'
    item_id = db.Column(db.String(50), index=True)
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed', 'skipped'
    message = db.Column(db.Text)
    details = db.Column(db.Text)  # JSON string for additional details
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<AutomationLog {self.action_type} - {self.status}>'


class Settings(db.Model):
    """Store application settings and preferences."""
    
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'


class PoshmarkListing(db.Model):
    """Track Poshmark listings scraped from users."""
    
    __tablename__ = 'poshmark_listings'
    
    id = db.Column(db.Integer, primary_key=True)
    poshmark_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    poshmark_url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float)
    original_price = db.Column(db.Float)
    description = db.Column(db.Text)
    brand = db.Column(db.String(100))
    size = db.Column(db.String(50))
    category = db.Column(db.String(100))
    condition = db.Column(db.String(50))
    seller_username = db.Column(db.String(100))
    images = db.Column(db.Text)  # JSON string of image URLs
    tags = db.Column(db.Text)    # JSON string of tags
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to eBay drafts
    ebay_drafts = db.relationship('EbayDraft', backref='poshmark_listing', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PoshmarkListing {self.poshmark_id}: {self.title}>'


class EbayDraft(db.Model):
    """Track eBay draft listings created from Poshmark listings."""
    
    __tablename__ = 'ebay_drafts'
    
    id = db.Column(db.Integer, primary_key=True)
    poshmark_listing_id = db.Column(db.Integer, db.ForeignKey('poshmark_listings.id'), nullable=False)
    ebay_item_id = db.Column(db.String(50), unique=True, index=True)  # Set when published
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    quantity = db.Column(db.Integer, default=1)
    category_id = db.Column(db.String(50))
    condition_id = db.Column(db.String(50))
    condition_description = db.Column(db.String(200))
    images = db.Column(db.Text)  # JSON string of image URLs
    location = db.Column(db.String(100), default='United States')
    listing_duration = db.Column(db.String(20), default='GTC')  # Good 'Til Cancelled
    listing_type = db.Column(db.String(20), default='FixedPriceItem')
    status = db.Column(db.String(20), default='draft')  # draft, published, failed
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    
    def __repr__(self):
        return f'<EbayDraft {self.id}: {self.title}>'


