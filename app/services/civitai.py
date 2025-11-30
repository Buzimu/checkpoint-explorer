"""
CivitAI integration service for model metadata scraping and version management
UPDATED VERSION - Extracts file sizes for version matching
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import json


class CivitAIService:
    """Service for interacting with CivitAI website"""
    
    def __init__(self):
        self.rate_limit_delay = 15  # 15 seconds between requests
        self.last_scrape_time = None
        self.activity_log = []
        self.max_activity_log = 10
    
    def can_scrape(self):
        """Check if enough time has passed since last scrape"""
        if not self.last_scrape_time:
            return True
        
        elapsed = (datetime.now() - self.last_scrape_time).total_seconds()
        return elapsed >= self.rate_limit_delay
    
    def wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit"""
        if not self.last_scrape_time:
            return
        
        elapsed = (datetime.now() - self.last_scrape_time).total_seconds()
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            print(f"⏳ Rate limit: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
    
    def log_activity(self, action, model_name, status='success', details=''):
        """Log an activity for the activity feed"""
        activity = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'modelName': model_name,
            'status': status,
            'details': details
        }
        
        self.activity_log.insert(0, activity)
        
        # Keep only last 10
        if len(self.activity_log) > self.max_activity_log:
            self.activity_log = self.activity_log[:self.max_activity_log]
        
        print(f"📝 Activity: {action} - {model_name} - {status}")
    
    def get_activity_log(self):
        """Get recent activity log"""
        return self.activity_log
    
    def extract_ids_from_url(self, url):
        """
        Extract model ID and version ID from CivitAI URL
        Examples:
        - https://civitai.com/models/1811313?modelVersionId=2176505
        - https://civitai.com/models/1811313/cool-model?modelVersionId=2176505
        """
        model_match = re.search(r'/models/(\d+)', url)
        version_match = re.search(r'modelVersionId=(\d+)', url)
        
        return {
            'modelId': model_match.group(1) if model_match else None,
            'versionId': version_match.group(1) if version_match else None
        }
    
    def scrape_model_page(self, civitai_url, model_name='Unknown'):
        """
        Scrape CivitAI model page for metadata
        
        Uses Next.js __NEXT_DATA__ JSON structure (Nov 2024)
        NOW INCLUDES: File sizes for version matching
        """
        try:
            # Wait for rate limit
            self.wait_for_rate_limit()
            
            # Extract IDs from URL first
            ids = self.extract_ids_from_url(civitai_url)
            if not ids['modelId']:
                self.log_activity('Scrape Failed', model_name, 'error', 'Invalid URL format')
                raise ValueError("Invalid CivitAI URL - cannot extract model ID")
            
            print(f"🔍 Scraping CivitAI model {ids['modelId']}...")
            
            # Make request with headers to look like a browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(civitai_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Update rate limit timestamp
            self.last_scrape_time = datetime.now()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract data from Next.js JSON
            next_data = self._extract_next_data(soup)
            if not next_data:
                raise ValueError("Could not find Next.js data in page")
            
            # Get model data from trpcState
            model_data = self._extract_model_from_trpc(next_data)
            if not model_data:
                raise ValueError("Could not extract model data from Next.js structure")
            
            # Extract tags from HTML (they're not always in JSON)
            tags = self._extract_tags_from_html(soup)
            
            # Build scraped data structure
            scraped_data = {
                'modelId': str(model_data.get('id', ids['modelId'])),
                'currentVersionId': ids['versionId'],
                'modelName': model_data.get('name', 'Unknown'),
                'description': self._clean_description(model_data.get('description', '')),
                'tags': tags,
                'trainedWords': self._extract_all_trained_words(model_data),
                'versions': self._extract_versions(model_data),
                'scrapedAt': datetime.now().isoformat()
            }
            
            print(f"✅ Scraped successfully: {scraped_data['modelName']}")
            print(f"   Found {len(scraped_data['versions'])} versions")
            print(f"   Tags: {', '.join(scraped_data['tags'][:5])}..." if scraped_data['tags'] else "   No tags")
            if scraped_data['trainedWords']:
                print(f"   Trigger words: {', '.join(scraped_data['trainedWords'][:3])}...")
            
            self.log_activity('Scrape Success', model_name, 'success', 
                            f"Found {len(scraped_data['versions'])} versions")
            
            return scraped_data
            
        except requests.RequestException as e:
            self.log_activity('Scrape Failed', model_name, 'error', f'Network error: {str(e)}')
            print(f"❌ Failed to scrape CivitAI: {e}")
            raise
        except Exception as e:
            self.log_activity('Scrape Failed', model_name, 'error', str(e))
            print(f"❌ Failed to parse CivitAI data: {e}")
            raise
    
    def _extract_next_data(self, soup):
        """Extract the Next.js __NEXT_DATA__ JSON from page"""
        script = soup.find('script', {'id': '__NEXT_DATA__'})
        if not script or not script.string:
            return None
        
        try:
            return json.loads(script.string)
        except json.JSONDecodeError:
            return None
    
    def _extract_model_from_trpc(self, next_data):
        """
        Extract model data from trpcState structure
        Structure: next_data['props']['pageProps']['trpcState']['json']['queries']
        Look for query with queryKey: [['model', 'getById'], ...]
        """
        try:
            trpc = next_data['props']['pageProps']['trpcState']['json']
            queries = trpc.get('queries', [])
            
            for query in queries:
                query_key = query.get('queryKey', [])
                
                # Check if this is the model query
                if (len(query_key) > 0 and 
                    isinstance(query_key[0], list) and 
                    len(query_key[0]) >= 2 and
                    query_key[0][0] == 'model' and 
                    query_key[0][1] == 'getById'):
                    
                    return query.get('state', {}).get('data', {})
            
            return None
        except (KeyError, TypeError, IndexError):
            return None
    
    def _clean_description(self, description):
        """Clean HTML from description"""
        if not description:
            return ""
        
        # Remove HTML tags
        soup = BeautifulSoup(description, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        # Limit length
        return text[:500] if len(text) > 500 else text
    
    def _extract_tags_from_html(self, soup):
        """
        Extract tags from HTML - they're in <a href="/tag/..."> links
        """
        tags = []
        
        tag_links = soup.find_all('a', href=re.compile(r'^/tag/'))
        
        for link in tag_links:
            href = link.get('href', '')
            tag_name = href.replace('/tag/', '').replace('%20', ' ')
            
            # Try to get cleaner name from badge label
            badge_label = link.find('span', class_=re.compile(r'Badge'))
            if badge_label:
                tag_name = badge_label.get_text(strip=True)
            
            if tag_name and tag_name not in tags:
                tags.append(tag_name)
        
        return tags[:15]  # Limit to 15 tags
    
    def _extract_all_trained_words(self, model_data):
        """
        Extract ALL unique trained words from ALL versions
        Trained words are at the VERSION level, not model level
        """
        all_words = []
        versions = model_data.get('modelVersions', [])
        
        for version in versions:
            words = version.get('trainedWords', [])
            for word in words:
                if word and word not in all_words:
                    all_words.append(word)
        
        return all_words
    
    def _extract_versions(self, model_data):
        """
        Extract version information from model data
        Each version has: id, name, status, trainedWords, files (with sizes), baseModel
        
        NEW: Extracts file sizes for version matching!
        """
        versions = []
        model_versions = model_data.get('modelVersions', [])
        
        for version in model_versions:
            # Extract file information (for version matching)
            files = []
            for file in version.get('files', []):
                # Get file size (may be in KB or bytes)
                size_kb = file.get('sizeKB', 0)
                
                # Some files have metadata with size info
                if size_kb == 0 and 'metadata' in file:
                    metadata = file['metadata']
                    if 'size' in metadata:
                        # Convert bytes to KB
                        size_kb = metadata['size'] / 1024
                
                file_info = {
                    'name': file.get('name', 'Unknown'),
                    'sizeKB': size_kb,
                    'type': file.get('type', 'Model'),
                    'format': file.get('metadata', {}).get('format', 'Unknown')
                }
                files.append(file_info)
            
            version_info = {
                'id': str(version.get('id', '')),
                'name': version.get('name', 'Unknown'),
                'status': version.get('status', 'Unknown'),
                'trainedWords': version.get('trainedWords', []),
                'available': version.get('status') == 'Published',
                'files': files,  # NEW: File size info for matching
                'baseModel': version.get('baseModel', 'Unknown')  # NEW: Base model info
            }
            versions.append(version_info)
        
        return versions


# Global service instance
_civitai_service = None

def get_civitai_service():
    """Get or create the global CivitAI service instance"""
    global _civitai_service
    if _civitai_service is None:
        _civitai_service = CivitAIService()
    return _civitai_service