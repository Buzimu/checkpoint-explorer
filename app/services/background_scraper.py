"""
Background scraping service - periodically scrapes CivitAI data
"""
import threading
import time
from datetime import datetime, timedelta
from app.services.database import load_db, save_db
from app.services.civitai import get_civitai_service


class BackgroundScraper:
    """Background task for periodic CivitAI scraping"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.scrape_interval = 60  # Seconds between scrape attempts
        self.daily_limit = 100  # Max scrapes per day
        self.scrapes_today = 0
        self.last_reset = datetime.now().date()
    
    def start(self):
        """Start the background scraping thread"""
        if self.running:
            print("⚠️ Background scraper already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scrape_loop, daemon=True)
        self.thread.start()
        print("✅ Background scraper started")
    
    def stop(self):
        """Stop the background scraping thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Background scraper stopped")
    
    def _reset_daily_counter(self):
        """Reset the daily scrape counter if it's a new day"""
        today = datetime.now().date()
        if today > self.last_reset:
            self.scrapes_today = 0
            self.last_reset = today
            print(f"📅 Daily scrape counter reset (limit: {self.daily_limit})")
    
    def _scrape_loop(self):
        """Main scraping loop - runs in background thread"""
        print("🔄 Background scraping loop started")
        
        while self.running:
            try:
                # Reset counter if new day
                self._reset_daily_counter()
                
                # Check if we've hit daily limit
                if self.scrapes_today >= self.daily_limit:
                    print(f"⏸️ Daily scrape limit reached ({self.daily_limit})")
                    time.sleep(self.scrape_interval)
                    continue
                
                # Get service
                service = get_civitai_service()
                
                # Check rate limit
                if not service.can_scrape():
                    time.sleep(5)  # Check again in 5 seconds
                    continue
                
                # Find a model to scrape
                model_to_scrape = self._find_eligible_model()
                
                if model_to_scrape:
                    self._scrape_model(model_to_scrape)
                    self.scrapes_today += 1
                else:
                    # No eligible models, wait longer
                    time.sleep(self.scrape_interval)
                
            except Exception as e:
                print(f"❌ Background scraper error: {e}")
                time.sleep(self.scrape_interval)
            
            # Wait before next attempt
            time.sleep(self.scrape_interval)
    
    def _find_eligible_model(self):
        """
        Find a model that needs scraping
        
        Eligible models:
        - Have a CivitAI URL
        - Haven't been scraped in the last 24 hours (or never scraped)
        - Not currently being scraped
        """
        db = load_db()
        
        eligible = []
        now = datetime.now()
        
        for model_path, model in db['models'].items():
            # Must have CivitAI URL
            if not model.get('civitaiUrl'):
                continue
            
            # Check last scrape time
            civitai_data = model.get('civitaiData', {})
            scraped_at = civitai_data.get('scrapedAt')
            
            if scraped_at:
                try:
                    last_scrape = datetime.fromisoformat(scraped_at)
                    hours_since = (now - last_scrape).total_seconds() / 3600
                    
                    # Only scrape if it's been 24+ hours
                    if hours_since < 24:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid date, treat as never scraped
            
            # This model is eligible
            eligible.append({
                'path': model_path,
                'name': model.get('name', 'Unknown'),
                'url': model['civitaiUrl']
            })
        
        # Return random model from eligible list
        if eligible:
            import random
            return random.choice(eligible)
        
        return None
    
    def _scrape_model(self, model_info):
        """Scrape a specific model and save results"""
        try:
            print(f"🔍 Background scraping: {model_info['name']}")
            
            # Get service and scrape
            service = get_civitai_service()
            scraped_data = service.scrape_model_page(
                model_info['url'],
                model_info['name']
            )
            
            # Load fresh DB
            db = load_db()
            
            if model_info['path'] not in db['models']:
                print(f"⚠️ Model {model_info['path']} no longer exists")
                return
            
            model = db['models'][model_info['path']]
            
            # Extract IDs
            ids = service.extract_ids_from_url(model_info['url'])
            model['civitaiModelId'] = ids['modelId']
            model['civitaiVersionId'] = ids['versionId']
            
            # Store scraped data
            model['civitaiData'] = scraped_data
            
            # Auto-fill tags if empty
            if not model.get('tags') or len(model['tags']) == 0:
                model['tags'] = scraped_data.get('tags', [])
            
            # Auto-fill trigger words if empty
            if not model.get('triggerWords') or len(model['triggerWords']) == 0:
                model['triggerWords'] = scraped_data.get('trainedWords', [])
            
            # Save
            if save_db(db):
                print(f"✅ Background scrape saved: {model_info['name']}")
            else:
                print(f"❌ Failed to save background scrape: {model_info['name']}")
            
        except Exception as e:
            print(f"❌ Background scrape failed for {model_info['name']}: {e}")


# Global background scraper instance
_background_scraper = None

def get_background_scraper():
    """Get or create the global background scraper instance"""
    global _background_scraper
    if _background_scraper is None:
        _background_scraper = BackgroundScraper()
    return _background_scraper