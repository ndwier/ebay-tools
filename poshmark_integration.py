"""Poshmark scraper integration for eBay tools."""
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import re

from models import db, PoshmarkListing, EbayDraft

logger = logging.getLogger(__name__)


class PoshmarkScraperIntegration:
    """Integration of Poshmark scraper with eBay tools system."""
    
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.base_url = "https://poshmark.com"
        
    def setup_driver(self):
        """Set up Chrome WebDriver with proper options."""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def scrape_user_listings(self, username: str = "ndwier") -> Dict:
        """Scrape all ACTIVE listings for a specific Poshmark user."""
        logger.info(f"Starting to scrape ACTIVE Poshmark listings for user: {username}")
        
        try:
            if not self.driver:
                self.setup_driver()
                
            listings = []
            # Only scrape ACTIVE listings using the availability=available parameter
            profile_url = f"{self.base_url}/closet/{username}?availability=available"
            
            self.driver.get(profile_url)
            logger.info(f"Accessing profile: {profile_url}")
            
            # Wait for the page to load
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "card"))
            )
            
            # Scroll to load more listings
            self._scroll_to_load_all()
            
            # Extract listing URLs
            listing_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='listing']")
            all_urls = [elem.get_attribute('href') for elem in listing_elements if elem.get_attribute('href')]
            
            # Remove duplicates
            listing_urls = list(set(all_urls))
            
            logger.info(f"Found {len(listing_urls)} unique listings for user {username}")
            
            # Scrape each listing
            for i, url in enumerate(listing_urls):
                try:
                    logger.info(f"Scraping listing {i+1}/{len(listing_urls)}: {url}")
                    listing_data = self._scrape_listing(url, username)
                    if listing_data:
                        listings.append(listing_data)
                    time.sleep(2)  # Be respectful
                except Exception as e:
                    logger.error(f"Error scraping listing {url}: {str(e)}")
                    continue
            
            # Save to database
            saved_count = self._save_listings_to_db(listings)
            
            return {
                'success': True,
                'username': username,
                'total_found': len(listing_urls),
                'successfully_scraped': len(listings),
                'saved_to_db': saved_count,
                'listings': listings
            }
            
        except Exception as e:
            logger.error(f"Error scraping user {username}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'username': username,
                'total_found': 0,
                'successfully_scraped': 0,
                'saved_to_db': 0,
                'listings': []
            }
    
    def _scroll_to_load_all(self):
        """Scroll down to load all listings dynamically."""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(2)
            
            # Check if we've reached the bottom
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    
    def _scrape_listing(self, listing_url: str, username: str) -> Optional[Dict]:
        """Scrape individual listing details."""
        try:
            self.driver.get(listing_url)
            time.sleep(3)  # Wait for page to load
            
            # Extract listing data
            listing_data = {
                'poshmark_id': self._extract_listing_id(listing_url),
                'poshmark_url': listing_url,
                'title': self._extract_title(),
                'price': self._extract_price(),
                'original_price': self._extract_original_price(),
                'description': self._extract_description(),
                'brand': self._extract_brand(),
                'size': self._extract_size(),
                'category': self._extract_category(),
                'condition': self._extract_condition(),
                'seller_username': username,
                'images': self._extract_images(),
                'tags': self._extract_tags()
            }
            
            return listing_data
            
        except Exception as e:
            logger.error(f"Error scraping listing {listing_url}: {str(e)}")
            return None
    
    def _extract_listing_id(self, url: str) -> str:
        """Extract listing ID from URL."""
        try:
            parts = url.split('/')
            for part in parts:
                if part.startswith('listing-'):
                    return part
            return url.split('/')[-1]
        except:
            return ""
    
    def _extract_title(self) -> str:
        """Extract listing title."""
        try:
            title = self.driver.title
            if title and " | " in title:
                return title.split(" | ")[0].strip()
            return "Unknown Item"
        except:
            return "Unknown Item"
    
    def _extract_price(self) -> float:
        """Extract current price."""
        try:
            elements_with_dollar = self.driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
            for element in elements_with_dollar:
                text = element.text.strip()
                if text.startswith('$') and len(text) < 20:
                    price_match = re.search(r'\$(\d+(?:\.\d{2})?)', text)
                    if price_match:
                        return float(price_match.group(1))
            return 10.00
        except:
            return 10.00
    
    def _extract_original_price(self) -> Optional[float]:
        """Extract original price if available."""
        try:
            original_price_element = self.driver.find_element(By.CSS_SELECTOR, ".original-price")
            price_text = original_price_element.text.strip().replace('$', '')
            return float(price_text)
        except:
            return None
    
    def _extract_description(self) -> str:
        """Extract listing description."""
        try:
            desc_element = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='listing-description']")
            return desc_element.text.strip()
        except:
            selectors = [".listing-description", ".description", "[class*='description']"]
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    return element.text.strip()
                except:
                    continue
            return ""
    
    def _extract_brand(self) -> str:
        """Extract brand information."""
        try:
            brand_element = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='listing-brand']")
            return brand_element.text.strip()
        except:
            return ""
    
    def _extract_size(self) -> str:
        """Extract size information."""
        try:
            size_element = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='listing-size']")
            return size_element.text.strip()
        except:
            return ""
    
    def _extract_category(self) -> str:
        """Extract category information."""
        try:
            category_element = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='listing-category']")
            return category_element.text.strip()
        except:
            try:
                breadcrumb = self.driver.find_element(By.CSS_SELECTOR, ".breadcrumb")
                return breadcrumb.text.strip()
            except:
                return ""
    
    def _extract_condition(self) -> str:
        """Extract condition information."""
        try:
            condition_element = self.driver.find_element(By.CSS_SELECTOR, "[data-test-id='listing-condition']")
            return condition_element.text.strip()
        except:
            return "Used"  # Default for Poshmark
    
    def _extract_images(self) -> List[str]:
        """Extract listing images."""
        images = []
        try:
            img_elements = self.driver.find_elements(By.TAG_NAME, "img")
            for img in img_elements:
                src = img.get_attribute('src')
                if src and 'cloudfront' in src and src.startswith('http'):
                    images.append(src)
            return list(set(images))[:12]  # Remove duplicates and limit to 12
        except Exception as e:
            logger.error(f"Error extracting images: {str(e)}")
            return []
    
    def _extract_tags(self) -> List[str]:
        """Extract tags/keywords from listing."""
        tags = []
        try:
            title = self._extract_title()
            description = self._extract_description()
            
            text = f"{title} {description}".lower()
            
            # Common fashion keywords
            keywords = ['vintage', 'designer', 'new', 'leather', 'cotton', 'silk', 'wool', 
                       'dress', 'shirt', 'pants', 'shoes', 'jacket', 'blazer', 'sweater']
            
            for keyword in keywords:
                if keyword in text:
                    tags.append(keyword)
                    
        except Exception as e:
            logger.error(f"Error extracting tags: {str(e)}")
        
        return tags
    
    def _save_listings_to_db(self, listings: List[Dict]) -> int:
        """Save scraped listings to database."""
        saved_count = 0
        
        for listing_data in listings:
            try:
                # Check if listing already exists
                existing = PoshmarkListing.query.filter_by(
                    poshmark_id=listing_data['poshmark_id']
                ).first()
                
                if existing:
                    # Update existing listing
                    existing.title = listing_data['title']
                    existing.price = listing_data['price']
                    existing.original_price = listing_data['original_price']
                    existing.description = listing_data['description']
                    existing.brand = listing_data['brand']
                    existing.size = listing_data['size']
                    existing.category = listing_data['category']
                    existing.condition = listing_data['condition']
                    existing.images = json.dumps(listing_data['images'])
                    existing.tags = json.dumps(listing_data['tags'])
                    existing.last_updated = datetime.utcnow()
                else:
                    # Create new listing
                    new_listing = PoshmarkListing(
                        poshmark_id=listing_data['poshmark_id'],
                        poshmark_url=listing_data['poshmark_url'],
                        title=listing_data['title'],
                        price=listing_data['price'],
                        original_price=listing_data['original_price'],
                        description=listing_data['description'],
                        brand=listing_data['brand'],
                        size=listing_data['size'],
                        category=listing_data['category'],
                        condition=listing_data['condition'],
                        seller_username=listing_data['seller_username'],
                        images=json.dumps(listing_data['images']),
                        tags=json.dumps(listing_data['tags'])
                    )
                    db.session.add(new_listing)
                
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving listing {listing_data.get('poshmark_id', 'unknown')}: {str(e)}")
                continue
        
        try:
            db.session.commit()
            logger.info(f"Successfully saved {saved_count} listings to database")
        except Exception as e:
            logger.error(f"Error committing listings to database: {str(e)}")
            db.session.rollback()
            saved_count = 0
        
        return saved_count
    
    def create_ebay_drafts_from_poshmark(self, poshmark_listing_ids: List[int]) -> Dict:
        """Create eBay drafts from Poshmark listings."""
        logger.info(f"Creating eBay drafts from {len(poshmark_listing_ids)} Poshmark listings")
        
        try:
            created_count = 0
            failed_count = 0
            
            for listing_id in poshmark_listing_ids:
                try:
                    poshmark_listing = PoshmarkListing.query.get(listing_id)
                    if not poshmark_listing:
                        logger.warning(f"Poshmark listing {listing_id} not found")
                        failed_count += 1
                        continue
                    
                    # Check if draft already exists
                    existing_draft = EbayDraft.query.filter_by(
                        poshmark_listing_id=listing_id
                    ).first()
                    
                    if existing_draft:
                        logger.info(f"Draft already exists for Poshmark listing {listing_id}")
                        continue
                    
                    # Create eBay draft
                    draft = self._create_draft_from_poshmark(poshmark_listing)
                    if draft:
                        created_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error creating draft for listing {listing_id}: {str(e)}")
                    failed_count += 1
            
            db.session.commit()
            
            return {
                'success': True,
                'created': created_count,
                'failed': failed_count,
                'total_processed': len(poshmark_listing_ids)
            }
            
        except Exception as e:
            logger.error(f"Error creating eBay drafts: {str(e)}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'created': 0,
                'failed': len(poshmark_listing_ids),
                'total_processed': len(poshmark_listing_ids)
            }
    
    def _create_draft_from_poshmark(self, poshmark_listing: PoshmarkListing) -> Optional[EbayDraft]:
        """Create an eBay draft from a Poshmark listing."""
        try:
            # Parse images and tags from JSON
            images = json.loads(poshmark_listing.images) if poshmark_listing.images else []
            tags = json.loads(poshmark_listing.tags) if poshmark_listing.tags else []
            
            # Map Poshmark condition to eBay condition
            condition_mapping = {
                'New with tags': '1000',  # New
                'New without tags': '1000',  # New
                'Like new': '1500',  # New other (see details)
                'Good': '3000',  # Used
                'Fair': '4000',  # Used
                'Used': '3000'  # Used
            }
            
            condition_id = condition_mapping.get(poshmark_listing.condition, '3000')
            
            # Create draft
            draft = EbayDraft(
                poshmark_listing_id=poshmark_listing.id,
                title=poshmark_listing.title,
                description=self._create_ebay_description(poshmark_listing),
                price=poshmark_listing.price,
                quantity=1,
                category_id=self._map_category_to_ebay(poshmark_listing.category),
                condition_id=condition_id,
                condition_description=poshmark_listing.condition,
                images=json.dumps(images),
                location='United States',
                listing_duration='GTC',
                listing_type='FixedPriceItem',
                status='draft'
            )
            
            db.session.add(draft)
            logger.info(f"Created draft for Poshmark listing: {poshmark_listing.title}")
            
            return draft
            
        except Exception as e:
            logger.error(f"Error creating draft from Poshmark listing {poshmark_listing.id}: {str(e)}")
            return None
    
    def _create_ebay_description(self, poshmark_listing: PoshmarkListing) -> str:
        """Create eBay description from Poshmark listing."""
        description_parts = []
        
        if poshmark_listing.description:
            description_parts.append(poshmark_listing.description)
        
        if poshmark_listing.brand:
            description_parts.append(f"Brand: {poshmark_listing.brand}")
        
        if poshmark_listing.size:
            description_parts.append(f"Size: {poshmark_listing.size}")
        
        if poshmark_listing.condition:
            description_parts.append(f"Condition: {poshmark_listing.condition}")
        
        description_parts.append("\nOriginally from Poshmark - Authentic item with detailed photos.")
        
        return "\n\n".join(description_parts)
    
    def _map_category_to_ebay(self, poshmark_category: str) -> str:
        """Map Poshmark category to eBay category ID."""
        category_mapping = {
            'Women': '1059',  # Women's Clothing
            'Men': '1059',    # Men's Clothing
            'Kids': '1059',   # Kids' Clothing
            'Shoes': '11450', # Women's Shoes
            'Handbags': '63852', # Handbags
            'Accessories': '1063', # Women's Accessories
            'Jewelry': '281', # Jewelry
            'Beauty': '26395', # Beauty
            'Home': '11700'   # Home & Garden
        }
        
        return category_mapping.get(poshmark_category, '1059')  # Default to Women's Clothing
    
    def close(self):
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
