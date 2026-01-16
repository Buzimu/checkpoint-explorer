"""
Background scraping service - periodically scrapes CivitAI data
UPDATED: Now includes automatic version linking after scraping
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
        self.daily_limit = 1000  # Max scrapes per day
        self.scrapes_today = 0
        self.last_reset = datetime.now().date()
        self.media_audit_interval = 300  # Run media audit every 5 minutes (300 seconds)
        self.last_media_audit = None  # Track when we last ran media audit
        self.last_healing_attempt = None  # Track last healing attempt time
        self.healing_rate_limit = 10  # Seconds between healing attempts
    
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
    
    def _check_media_audit(self):
        """Check if it's time to run periodic media audit"""
        now = datetime.now()
        
        if self.last_media_audit is None:
            # First run - do it now
            self._run_full_media_audit()
            self.last_media_audit = now
            return
        
        elapsed = (now - self.last_media_audit).total_seconds()
        if elapsed >= self.media_audit_interval:
            self._run_full_media_audit()
            self.last_media_audit = now
    
    def _run_full_media_audit(self):
        """Run full media audit across all models"""
        try:
            from app.services.media_auditor import audit_all_media
            from app.services.civitai import get_civitai_service
            
            print("\n🔍 Running scheduled full media audit...")
            db = load_db()
            audit_results = audit_all_media(db)
            
            total_added = audit_results.get('total_added', 0)
            total_removed = audit_results.get('total_removed', 0)
            total_verified = audit_results.get('total_verified', 0)
            
            if total_added > 0 or total_removed > 0:
                save_db(db)
                print(f"✅ Media audit complete: verified={total_verified}, removed={total_removed}, added={total_added}")
                
                # Log activity
                service = get_civitai_service()
                details = f"verified={total_verified}, removed={total_removed}, added={total_added}"
                service.log_activity('Media Audit', 'All Models', 'success', details)
            else:
                print(f"✅ Media audit complete: all {total_verified} files verified")
        except Exception as e:
            print(f"❌ Scheduled media audit failed: {e}")
            try:
                service = get_civitai_service()
                service.log_activity('Media Audit', 'All Models', 'error', str(e))
            except:
                pass
    
    def _can_attempt_healing(self):
        """Check if enough time has passed since last healing attempt"""
        if self.last_healing_attempt is None:
            return True
        
        now = datetime.now()
        elapsed = (now - self.last_healing_attempt).total_seconds()
        return elapsed >= self.healing_rate_limit
    
    def _find_model_needing_healing(self):
        """
        Find a model that needs URL healing
        
        Eligible models:
        - Have a valid SHA256 hash
        - Missing CivitAI URL (empty or None)
        - Haven't failed healing in the last 24 hours
        """
        db = load_db()
        
        eligible = []
        now = datetime.now()
        
        total_models = len(db['models'])
        no_hash_count = 0
        has_url_count = 0
        recently_attempted_count = 0
        
        for model_path, model in db['models'].items():
            # Must have a hash
            file_hash = model.get('fileHash')
            if not file_hash:
                no_hash_count += 1
                continue
            
            # Must be missing URL
            civitai_url = model.get('civitaiUrl', '').strip()
            civitai_model_id = model.get('civitaiModelId', '').strip()
            if civitai_url or civitai_model_id:
                has_url_count += 1
                continue  # Already has URL or model ID
            
            # Check if healing failed recently (within last 24 hours)
            civitai_data = model.get('civitaiData', {})
            healing_attempted = civitai_data.get('healingAttempted')
            if healing_attempted:
                try:
                    last_attempt = datetime.fromisoformat(healing_attempted)
                    hours_since = (now - last_attempt).total_seconds() / 3600
                    
                    # Skip if attempted less than 24 hours ago
                    if hours_since < 24:
                        recently_attempted_count += 1
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid date, treat as never attempted
            
            # Add to eligible list with priority (never attempted first)
            priority = 0 if not healing_attempted else 1
            eligible.append((priority, model_path, model))
        
        # Debug output
        if not eligible:
            print(f"🔍 Healing scan: {total_models} total, {no_hash_count} no hash, {has_url_count} have URL, {recently_attempted_count} recently attempted, 0 eligible")
            return None
        
        print(f"🔍 Healing scan: {total_models} total, {len(eligible)} eligible for healing")
        
        # Sort by priority (never attempted first)
        eligible.sort(key=lambda x: x[0])
        
        # Return the highest priority model
        return eligible[0][1]  # Return just the path
    
    def _heal_model(self, model_path):
        """Attempt to heal a single model's missing URL"""
        try:
            from app.services.self_healing import SelfHealingService
            from app.services.civitai import get_civitai_service
            from app.services.database import save_db
            
            db = load_db()
            model = db['models'].get(model_path)
            if not model:
                return
            
            model_name = model.get('name', model_path.split('/')[-1])
            print(f"\n🩹 Attempting to heal: {model_name}")
            
            healing_service = SelfHealingService()
            result = healing_service.heal_model(model_path, model)
            
            # Update healing attempt timestamp regardless of success
            if 'civitaiData' not in model:
                model['civitaiData'] = {}
            model['civitaiData']['healingAttempted'] = datetime.now().isoformat()
            
            if result.get('success'):
                print(f"✅ Healed: {model_name} → {result.get('url', 'URL recovered')}")
                
                # Log success
                service = get_civitai_service()
                service.log_activity('Self-Healing', model_name, 'success', result.get('message', 'URL recovered'))
            else:
                print(f"⚠️ Could not heal: {model_name} - {result.get('message', 'Not found in archive')}")
            
            # Save DB with updated healing timestamp
            save_db(db)
            
        except Exception as e:
            print(f"❌ Healing failed for {model_path}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_next_scrape_model(self):
        """Get the name of the next model that will be scraped"""
        model_info = self._find_eligible_model()
        if model_info:
            # _find_eligible_model returns a dict with 'path' and 'name'
            return model_info.get('name', 'Unknown')
        return None
    
    def get_next_healing_model(self):
        """Get the name of the next model that will be healed"""
        model_path = self._find_model_needing_healing()
        if model_path:
            # _find_model_needing_healing returns a string path
            db = load_db()
            model = db['models'].get(model_path)
            if model:
                return model.get('name', model_path.split('/')[-1])
        return None
    
    def _scrape_loop(self):
        """Main scraping loop - runs in background thread"""
        print("🔄 Background scraping loop started")
        
        while self.running:
            try:
                # Reset counter if new day
                self._reset_daily_counter()
                
                # Check if we need to run periodic media audit
                self._check_media_audit()
                
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
                    
                    # After scraping, check if we can also heal a model
                    if self._can_attempt_healing():
                        model_to_heal = self._find_model_needing_healing()
                        if model_to_heal:
                            self._heal_model(model_to_heal)
                            self.last_healing_attempt = datetime.now()
                else:
                    # No models to scrape, try healing instead
                    if self._can_attempt_healing():
                        model_to_heal = self._find_model_needing_healing()
                        if model_to_heal:
                            self._heal_model(model_to_heal)
                            self.last_healing_attempt = datetime.now()
                        else:
                            # Nothing to do
                            print("💤 No eligible models to scrape or heal")
                            time.sleep(self.scrape_interval)
                    else:
                        # Wait for healing rate limit
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
        - Have a valid CivitAI URL (contains /models/ with numeric ID)
        - Haven't been scraped in the last 24 hours (or never scraped)
        - Haven't failed scraping in the last hour
        - Not currently being scraped
        """
        db = load_db()
        
        eligible = []
        now = datetime.now()
        
        for model_path, model in db['models'].items():
            # Must have CivitAI URL
            civitai_url = model.get('civitaiUrl', '').strip()
            if not civitai_url:
                continue
            
            # Validate URL format (must have /models/ and a numeric ID)
            if '/models/' not in civitai_url:
                continue
            
            # Quick validation - try to extract model ID
            import re
            model_match = re.search(r'/models/(\d+)', civitai_url)
            if not model_match:
                # Invalid URL format, skip this model permanently
                continue
            
            # Check if scraping failed recently (within last hour)
            civitai_data = model.get('civitaiData', {})
            last_error = civitai_data.get('lastError')
            if last_error:
                try:
                    error_time = datetime.fromisoformat(last_error)
                    hours_since_error = (now - error_time).total_seconds() / 3600
                    
                    # Skip if error was less than 1 hour ago
                    if hours_since_error < 1:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid date, ignore
            
            # Check last scrape time
            scraped_at = civitai_data.get('scrapedAt')
            
            if scraped_at:
                try:
                    last_scrape = datetime.fromisoformat(scraped_at)
                    hours_since = (now - last_scrape).total_seconds() / 3600
                    
                    # Only scrape if it's been 1+ hours
                    if hours_since < 1:
                        continue
                except (ValueError, TypeError):
                    pass  # Invalid date, treat as never scraped
            
            # This model is eligible
            eligible.append({
                'path': model_path,
                'name': model.get('name', 'Unknown'),
                'url': civitai_url
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
            
            # Clear any previous error (scrape succeeded)
            if 'lastError' in model['civitaiData']:
                del model['civitaiData']['lastError']
            
            # Auto-fill tags if empty
            if not model.get('tags') or len(model['tags']) == 0:
                model['tags'] = scraped_data.get('tags', [])
            
            # Auto-fill trigger words if empty
            if not model.get('triggerWords') or len(model['triggerWords']) == 0:
                model['triggerWords'] = scraped_data.get('trainedWords', [])
            
            # Save the scraped data first
            if save_db(db):
                print(f"✅ Background scrape saved: {model_info['name']}")
            else:
                print(f"❌ Failed to save background scrape: {model_info['name']}")
                return
            
            # ====================================================================
            # AUTO-LINK RELATED VERSIONS (after saving scraped data)
            # ====================================================================
            from app.services.civitai_version_linking import link_versions_from_civitai_scrape, detect_newer_versions
            
            try:
                linking_result = link_versions_from_civitai_scrape(model_info['path'], scraped_data)
                
                if linking_result:
                    stats = linking_result.get('stats', {})
                    if stats.get('confirmed', 0) > 0 or stats.get('assumed', 0) > 0:
                        print(f"🔗 Auto-linked versions: {stats.get('confirmed', 0)} confirmed, {stats.get('assumed', 0)} assumed")
            except Exception as link_error:
                print(f"⚠️ Version linking failed: {link_error}")
            
            # ====================================================================
            # AUTO-DETECT NEWER VERSIONS (after scrape)
            # ====================================================================
            try:
                print(f"🔍 Checking for newer versions after background scrape...")
                db = load_db()  # Reload to get latest links
                newer_versions_info = detect_newer_versions(db)
                
                # Update the model's newVersionAvailable flag
                if model_info['path'] in newer_versions_info:
                    db['models'][model_info['path']]['newVersionAvailable'] = newer_versions_info[model_info['path']]
                    print(f"   ✨ Newer version detected for {model_info['path']}")
                    
                    # Log activity
                    service = get_civitai_service()
                    service.log_activity('Newer Version Found', model_info['name'], 'success', 'Update available')
                elif 'newVersionAvailable' in db['models'][model_info['path']]:
                    del db['models'][model_info['path']]['newVersionAvailable']
                    print(f"   ✅ Model is up to date")
                
                save_db(db)
            except Exception as detect_error:
                print(f"⚠️  Newer version detection failed (non-critical): {detect_error}")
            
            # ====================================================================
            # RUN MEDIA AUDITOR (after scrape)
            # ====================================================================
            try:
                from app.services.media_auditor import audit_media_for_model
                print(f"🔍 Running media audit for {model_info['path']}...")
                db = load_db()
                audit_stats = audit_media_for_model(db, model_info['path'], db['models'][model_info['path']])
                if audit_stats['removed'] > 0 or audit_stats['added'] > 0:
                    save_db(db)
                    print(f"   Media audit: verified={audit_stats['verified']}, removed={audit_stats['removed']}, added={audit_stats['added']}")
            except Exception as audit_error:
                print(f"⚠️  Media audit failed (non-critical): {audit_error}")
            
        except Exception as e:
            print(f"❌ Background scrape failed for {model_info['name']}: {e}")
            
            # Record the error and timestamp
            try:
                db = load_db()
                if model_info['path'] in db['models']:
                    model = db['models'][model_info['path']]
                    
                    # Ensure civitaiData exists
                    if 'civitaiData' not in model:
                        model['civitaiData'] = {}
                    
                    # Record error and timestamp
                    model['civitaiData']['lastError'] = datetime.now().isoformat()
                    model['civitaiData']['lastErrorMessage'] = str(e)
                    
                    save_db(db)
                    print(f"📝 Recorded error for {model_info['name']} - will retry in 1 hour")
            except Exception as save_error:
                print(f"⚠️ Failed to record error: {save_error}")


# Global background scraper instance
_background_scraper = None

def get_background_scraper():
    """Get or create the global background scraper instance"""
    global _background_scraper
    if _background_scraper is None:
        _background_scraper = BackgroundScraper()
    return _background_scraper