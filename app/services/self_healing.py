"""
Self-Healing Service for automatic URL recovery
Coordinates between CivArchive, CivitAI, and database services
"""
from datetime import datetime
import time
from app.services.civarchive import get_civarchive_service
from app.services.civitai import get_civitai_service
from app.services.database import load_db, save_db


class SelfHealingService:
    """
    Service for automatically recovering missing URLs using archive sources
    """
    
    def __init__(self):
        self.civarchive = get_civarchive_service()
        self.civitai = get_civitai_service()
        self.healing_log = []
        self.max_log_size = 50
    
    def heal_model(self, model_path, model_data):
        """
        Attempt to heal a single model by finding its URL
        
        Args:
            model_path: Path to the model file (database key)
            model_data: Current model data from database
        
        Returns:
            dict: Healing result with status and any recovered data
        """
        result = {
            'modelPath': model_path,
            'modelName': model_data.get('name', 'Unknown'),
            'success': False,
            'action': 'none',
            'previousUrl': model_data.get('civitaiUrl'),
            'newUrl': None,
            'source': None,
            'metadata': {},
            'timestamp': datetime.now().isoformat(),
            'message': ''
        }
        
        try:
            # Check if model needs healing
            file_hash = model_data.get('fileHash')
            civitai_url = model_data.get('civitaiUrl')
            
            if not file_hash:
                result['message'] = 'No hash available - cannot search'
                result['action'] = 'skipped_no_hash'
                return result
            
            if civitai_url and civitai_url.strip():
                result['message'] = 'URL already present - no healing needed'
                result['action'] = 'skipped_has_url'
                return result
            
            print(f"\n{'='*70}")
            print(f"🔧 Attempting to heal: {result['modelName']}")
            print(f"   Path: {model_path}")
            print(f"   Hash: {file_hash[:16]}...")
            print(f"{'='*70}")
            
            # Step 1: Search archive for the hash
            archive_result = self.civarchive.search_by_hash(file_hash)
            
            if 'error' in archive_result:
                result['message'] = f"Archive search error: {archive_result['error']}"
                result['action'] = 'error_archive_search'
                result['metadata']['archiveError'] = archive_result['error']
                return result
            
            if not archive_result['found'] or not archive_result['results']:
                result['message'] = 'Model not found in archive'
                result['action'] = 'not_found_in_archive'
                return result
            
            # Step 2: Process search results
            print(f"\n📋 Found {len(archive_result['results'])} result(s) in archive")
            
            # Prioritize CivitAI results
            civitai_results = [r for r in archive_result['results'] if r['source'] == 'civitai']
            other_results = [r for r in archive_result['results'] if r['source'] != 'civitai']
            
            # Try CivitAI first
            if civitai_results:
                heal_result = self._heal_from_civitai(
                    civitai_results[0], 
                    model_data, 
                    file_hash
                )
                if heal_result['success']:
                    result.update(heal_result)
                    # Update the model_data dict with the healed information
                    self._apply_healing_to_model(model_data, result)
                    return result
            
            # Fallback to other sources
            if other_results:
                heal_result = self._heal_from_other_source(
                    other_results[0], 
                    model_data
                )
                if heal_result['success']:
                    result.update(heal_result)
                    # Update the model_data dict with the healed information
                    self._apply_healing_to_model(model_data, result)
                    return result
            
            result['message'] = 'Found in archive but could not recover URL'
            result['action'] = 'found_but_failed'
            
        except Exception as e:
            print(f"❌ Healing error: {e}")
            result['message'] = f"Healing failed: {str(e)}"
            result['action'] = 'error_exception'
            result['metadata']['exception'] = str(e)
        
        finally:
            # Log this healing attempt
            self._log_healing(result)
        
        return result
    
    def _heal_from_civitai(self, archive_result, model_data, file_hash):
        """
        Heal a model using a CivitAI result from the archive
        
        Args:
            archive_result: Result from archive search (for CivitAI)
            model_data: Current model data
            file_hash: SHA256 hash of the file
        
        Returns:
            dict: Healing result
        """
        result = {
            'success': False,
            'action': 'none',
            'newUrl': None,
            'source': 'civitai',
            'metadata': {}
        }
        
        civitai_url = archive_result['url']
        status = archive_result['status']
        
        print(f"\n🎯 Processing CivitAI result:")
        print(f"   URL: {civitai_url}")
        print(f"   Status: {status}")
        
        # If the URL is live, scrape it
        if status == 'live':
            try:
                print(f"   ✅ Original page is live - scraping...")
                
                # Scrape the CivitAI page
                scraped = self.civitai.scrape_model_page(
                    civitai_url, 
                    model_data.get('name', 'Unknown')
                )
                
                # Verify hash matches one of the versions
                hash_match = self._verify_hash_in_versions(file_hash, scraped['versions'])
                
                if hash_match:
                    result['success'] = True
                    result['action'] = 'url_recovered_live'
                    result['newUrl'] = self._build_version_url(
                        civitai_url, 
                        hash_match['versionId']
                    )
                    result['message'] = f"Recovered live CivitAI URL (version: {hash_match['versionName']})"
                    result['metadata'] = {
                        'versionId': hash_match['versionId'],
                        'versionName': hash_match['versionName'],
                        'matchedHash': file_hash,
                        'confidence': 'high',
                        'scrapedData': scraped
                    }
                else:
                    result['message'] = 'Live URL found but hash does not match any version'
                    result['action'] = 'found_but_no_hash_match'
                    result['metadata']['availableVersions'] = len(scraped['versions'])
                
            except Exception as e:
                print(f"   ❌ Failed to scrape live URL: {e}")
                result['message'] = f"Live URL found but scraping failed: {str(e)}"
                result['action'] = 'error_scraping_live'
                result['metadata']['scrapingError'] = str(e)
        
        # If deleted, we could use archive snapshot data
        elif status == 'deleted':
            result['action'] = 'found_but_deleted'
            result['message'] = 'Found in archive but original page is deleted'
            result['metadata']['deletedUrl'] = civitai_url
            result['metadata']['archiveUrl'] = archive_result.get('archiveUrl')
            
            # TODO: Future enhancement - extract data from archived snapshot
            # For now, we'll just store the deleted URL for reference
            result['newUrl'] = civitai_url  # Store it anyway for reference
            result['success'] = True  # Mark as success so we record it
        
        else:
            result['message'] = f"Found in archive but status is '{status}'"
            result['action'] = 'found_but_unknown_status'
        
        return result
    
    def _heal_from_other_source(self, archive_result, model_data):
        """
        Heal a model using a non-CivitAI source (HuggingFace, etc.)
        
        Args:
            archive_result: Result from archive search (non-CivitAI)
            model_data: Current model data
        
        Returns:
            dict: Healing result
        """
        result = {
            'success': True,
            'action': 'url_recovered_other',
            'newUrl': archive_result['url'],
            'source': archive_result['source'],
            'message': f"Found {archive_result['source']} URL in archive",
            'metadata': {
                'sourcePlatform': archive_result['source'],
                'archiveUrl': archive_result.get('archiveUrl')
            }
        }
        
        print(f"\n🔗 Found non-CivitAI source: {archive_result['source']}")
        print(f"   URL: {archive_result['url']}")
        
        return result
    
    def _verify_hash_in_versions(self, target_hash, versions):
        """
        Check if the target hash exists in any of the scraped versions
        
        Args:
            target_hash: SHA256 hash to find
            versions: List of version data from CivitAI scrape
        
        Returns:
            dict: Version info if found, None otherwise
        """
        target_hash_lower = target_hash.lower()
        
        for version in versions:
            for file in version.get('files', []):
                file_hash = file.get('hash', '')
                if file_hash and file_hash.lower() == target_hash_lower:
                    return {
                        'versionId': version['id'],
                        'versionName': version['name'],
                        'fileName': file['name'],
                        'fileSize': file.get('sizeKB', 0)
                    }
        
        return None
    
    def _build_version_url(self, base_url, version_id):
        """
        Build the correct CivitAI URL with version ID
        
        Args:
            base_url: Original CivitAI URL (may or may not have versionId)
            version_id: Version ID to use
        
        Returns:
            str: URL with correct version parameter
        """
        # Extract model ID from URL
        import re
        model_match = re.search(r'/models/(\d+)', base_url)
        if not model_match:
            return base_url
        
        model_id = model_match.group(1)
        return f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
    
    def heal_all_models(self, limit=None, skip_existing=True):
        """
        Attempt to heal all models in the database
        
        Args:
            limit: Maximum number of models to process (None for all)
            skip_existing: Skip models that already have a civitaiUrl
        
        Returns:
            dict: Summary of healing results
        """
        print(f"\n{'='*70}")
        print(f"🏥 Starting batch healing process")
        print(f"{'='*70}\n")
        
        db = load_db()
        models = db.get('models', {})
        
        summary = {
            'total': 0,
            'processed': 0,
            'skipped': 0,
            'success': 0,
            'failed': 0,
            'results': [],
            'startedAt': datetime.now().isoformat()
        }
        
        models_to_process = []
        for path, data in models.items():
            if skip_existing and data.get('civitaiUrl'):
                continue
            models_to_process.append((path, data))
        
        summary['total'] = len(models_to_process)
        
        if limit:
            models_to_process = models_to_process[:limit]
            print(f"📊 Processing {len(models_to_process)} of {summary['total']} models (limit={limit})")
        else:
            print(f"📊 Processing all {len(models_to_process)} models without URLs")
        
        for i, (path, data) in enumerate(models_to_process, 1):
            print(f"\n[{i}/{len(models_to_process)}] Processing: {path}")
            
            result = self.heal_model(path, data)
            summary['processed'] += 1
            
            if result['action'].startswith('skipped'):
                summary['skipped'] += 1
            elif result['success']:
                summary['success'] += 1
                # Update the database
                self._update_model_in_db(path, result, db)
            else:
                summary['failed'] += 1
            
            summary['results'].append(result)
            
            # Rate limiting between models
            if i < len(models_to_process):
                print("   ⏳ Waiting 5 seconds before next model...")
                time.sleep(5)
        
        # Save database if any changes were made
        if summary['success'] > 0:
            save_db(db)
            print(f"\n💾 Database updated with {summary['success']} recovered URLs")
        
        summary['completedAt'] = datetime.now().isoformat()
        
        print(f"\n{'='*70}")
        print(f"🏥 Batch healing complete")
        print(f"{'='*70}")
        print(f"   Processed: {summary['processed']}")
        print(f"   Success:   {summary['success']}")
        print(f"   Failed:    {summary['failed']}")
        print(f"   Skipped:   {summary['skipped']}")
        print(f"{'='*70}\n")
        
        return summary
    
    def _apply_healing_to_model(self, model, healing_result):
        """
        Apply healing results directly to a model dictionary
        
        Args:
            model: Model dict to update (modified in place)
            healing_result: Result from healing process
        """
        if not healing_result.get('success') or not healing_result.get('newUrl'):
            return
        
        # Update URL and IDs based on source
        if healing_result['source'] == 'civitai':
            # Extract model ID and version ID from URL
            from app.services.civitai import get_civitai_service
            service = get_civitai_service()
            ids = service.extract_ids_from_url(healing_result['newUrl'])
            
            # Set both the URL and the IDs (IDs are what the app actually uses)
            model['civitaiUrl'] = healing_result['newUrl']
            model['civitaiModelId'] = ids['modelId']
            if ids.get('versionId'):
                model['civitaiVersionId'] = ids['versionId']
            
            print(f"   ✅ Updated model: civitaiModelId={ids['modelId']}, civitaiVersionId={ids.get('versionId')}")
        elif healing_result['source'] == 'huggingface':
            model['huggingFaceUrl'] = healing_result['newUrl']
        else:
            model['otherUrl'] = healing_result['newUrl']
        
        # Add healing history
        if 'healingHistory' not in model:
            model['healingHistory'] = []
        
        model['healingHistory'].append({
            'timestamp': healing_result['timestamp'],
            'action': healing_result['action'],
            'source': healing_result['source'],
            'url': healing_result['newUrl'],
            'message': healing_result['message']
        })
        
        # If we have scraped data, optionally update model metadata
        if 'scrapedData' in healing_result.get('metadata', {}):
            scraped = healing_result['metadata']['scrapedData']
            
            # Update tags if empty
            if not model.get('tags'):
                model['tags'] = scraped.get('tags', [])
            
            # Update trigger words if empty
            if not model.get('triggerWords'):
                model['triggerWords'] = scraped.get('trainedWords', [])
    
    def _update_model_in_db(self, model_path, healing_result, db):
        """
        Update a model in the database with healed data
        
        Args:
            model_path: Path to the model (database key)
            healing_result: Result from healing process
            db: Database dict (will be modified)
        """
        model = db['models'].get(model_path)
        if not model:
            return
        
        # Update URL and IDs based on source
        if healing_result['source'] == 'civitai':
            # Extract model ID and version ID from URL
            from app.services.civitai import get_civitai_service
            service = get_civitai_service()
            ids = service.extract_ids_from_url(healing_result['newUrl'])
            
            # Set both the URL and the IDs (IDs are what the app actually uses)
            model['civitaiUrl'] = healing_result['newUrl']
            model['civitaiModelId'] = ids['modelId']
            if ids.get('versionId'):
                model['civitaiVersionId'] = ids['versionId']
        elif healing_result['source'] == 'huggingface':
            model['huggingFaceUrl'] = healing_result['newUrl']
        else:
            model['otherUrl'] = healing_result['newUrl']
        
        # Add healing history
        if 'healingHistory' not in model:
            model['healingHistory'] = []
        
        model['healingHistory'].append({
            'timestamp': healing_result['timestamp'],
            'action': healing_result['action'],
            'source': healing_result['source'],
            'url': healing_result['newUrl'],
            'message': healing_result['message']
        })
        
        # If we have scraped data, optionally update model metadata
        if 'scrapedData' in healing_result.get('metadata', {}):
            scraped = healing_result['metadata']['scrapedData']
            
            # Update tags if empty
            if not model.get('tags'):
                model['tags'] = scraped.get('tags', [])
            
            # Update trigger words if empty
            if not model.get('triggerWords'):
                model['triggerWords'] = scraped.get('trainedWords', [])
        
        print(f"   ✅ Updated database entry for {model_path}")
    
    def _log_healing(self, result):
        """Log a healing attempt"""
        self.healing_log.insert(0, result)
        
        # Keep log size manageable
        if len(self.healing_log) > self.max_log_size:
            self.healing_log = self.healing_log[:self.max_log_size]
    
    def get_healing_log(self):
        """Get recent healing attempts"""
        return self.healing_log
    
    def get_models_needing_healing(self):
        """
        Get a list of models that could benefit from healing
        
        Returns:
            list: Models with missing URLs but with hashes
        """
        db = load_db()
        models = db.get('models', {})
        
        needs_healing = []
        
        for path, data in models.items():
            if not data.get('civitaiUrl') and data.get('fileHash'):
                needs_healing.append({
                    'path': path,
                    'name': data.get('name', 'Unknown'),
                    'hash': data.get('fileHash'),
                    'modelType': data.get('modelType'),
                    'fileSize': data.get('fileSizeFormatted')
                })
        
        return needs_healing


# Global service instance
_self_healing_service = None

def get_self_healing_service():
    """Get or create the global self-healing service instance"""
    global _self_healing_service
    if _self_healing_service is None:
        _self_healing_service = SelfHealingService()
    return _self_healing_service
