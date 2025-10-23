"""Configuration management for eBay automation tool."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration."""
    
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    PORT = int(os.getenv('FLASK_PORT', 5001))
    
    # Database
    DATABASE_PATH = os.getenv('DATABASE_PATH', './data/ebay_automation.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # eBay API credentials
    EBAY_APP_ID = os.getenv('EBAY_APP_ID')
    EBAY_CERT_ID = os.getenv('EBAY_CERT_ID')
    EBAY_DEV_ID = os.getenv('EBAY_DEV_ID')
    EBAY_TOKEN = os.getenv('EBAY_TOKEN')
    EBAY_ENV = os.getenv('EBAY_ENV', 'production')
    
    # Automation settings
    STALE_LISTING_DAYS = int(os.getenv('STALE_LISTING_DAYS', 30))
    MIN_VIEWS_FOR_OFFER = int(os.getenv('MIN_VIEWS_FOR_OFFER', 5))
    OFFER_DISCOUNT_PERCENT = float(os.getenv('OFFER_DISCOUNT_PERCENT', 10))
    FEEDBACK_REQUEST_DAYS = int(os.getenv('FEEDBACK_REQUEST_DAYS', 7))
    
    # Scheduler settings
    STALE_CHECK_SCHEDULE = os.getenv('STALE_CHECK_SCHEDULE', '0 2 * * *')
    OFFER_CHECK_SCHEDULE = os.getenv('OFFER_CHECK_SCHEDULE', '0 10 * * *')
    FEEDBACK_CHECK_SCHEDULE = os.getenv('FEEDBACK_CHECK_SCHEDULE', '0 15 * * *')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @staticmethod
    def validate():
        """Validate required configuration."""
        required = [
            'EBAY_APP_ID',
            'EBAY_CERT_ID',
            'EBAY_DEV_ID',
            'EBAY_TOKEN'
        ]
        missing = []
        for key in required:
            if not getattr(Config, key):
                missing.append(key)
        
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Please check your .env file."
            )
        
        return True


