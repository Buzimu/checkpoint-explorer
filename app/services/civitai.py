"""
CivitAI integration service for model metadata scraping and version management
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
    
    def _extract_air_code(self, soup):
        """
        Extract AIR code from page which contains modelId@versionId
        Format: civitai:453428@2311163
        Returns: {'modelId': '453428', 'versionId': '2311163'}
        """
        # Find all code elements
        codes = soup.find_all('code')
        
        # Look for pattern: civitai: modelId @ versionId
        model_id = None
        version_id = None
        
        for i, code in enumerate(codes):
            text = code.get_text(strip=True)
            
            # Check if this is "civitai:"
            if text == 'civitai:':
                # Next code should be model ID
                if i + 1 < len(codes):
                    next_text = codes[i + 1].get_text(strip=True)
                    if next_text.isdigit():
                        model_id = next_text
                        
                        # Check for @ symbol and version ID
                        if i + 3 < len(codes):
                            at_symbol = codes[i + 2].get_text(strip=True)
                            version_text = codes[i + 3].get_text(strip=True)
                            
                            if at_symbol == '@' and version_text.isdigit():
                                version_id = version_text
                                break
        
        return {
            'modelId': model_id,
            'versionId': version_id
        }
    
    def scrape_model_page(self, civitai_url, model_name='Unknown'):
        """
        Scrape CivitAI model page for metadata
        
        Uses actual CivitAI HTML structure as of Nov 2024
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
            
            # Try to extract AIR code for more accurate IDs
            air_ids = self._extract_air_code(soup)
            if air_ids['modelId']:
                ids['modelId'] = air_ids['modelId']
            if air_ids['versionId']:
                ids['versionId'] = air_ids['versionId']
            
            # Extract data
            scraped_data = {
                'modelId': ids['modelId'],
                'currentVersionId': ids['versionId'],
                'modelName': self._extract_model_name(soup),
                'description': self._extract_description(soup),
                'tags': self._extract_tags(soup),
                'trainedWords': self._extract_trigger_words(soup),
                'versions': self._extract_versions(soup, ids['modelId']),
                'scrapedAt': datetime.now().isoformat()
            }
            
            print(f"✅ Scraped successfully: {scraped_data['modelName']}")
            print(f"   Found {len(scraped_data['versions'])} versions")
            print(f"   Tags: {', '.join(scraped_data['tags'][:5])}...")
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
    
    def _extract_model_name(self, soup):
        """Extract model name from page - look for h1 or title"""
        # Try h1 first
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        # Try page title
        title = soup.find('title')
        if title:
            text = title.get_text(strip=True)
            # Remove " - Civitai" suffix if present
            if ' - ' in text:
                return text.split(' - ')[0]
            return text
        
        return "Unknown Model"
    
    def _extract_description(self, soup):
        """Extract model description from page"""
        # Look for description in meta tags first
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content']
        
        # Try to find description section
        # CivitAI often has description in article or specific div
        desc_section = soup.find('article')
        if desc_section:
            return desc_section.get_text(strip=True)[:500]  # Limit length
        
        return ""
    
    def _extract_tags(self, soup):
        """
        Extract tags from page
        Tags are in: <a href="/tag/tagname"><span class="mantine-Badge-label">tagname</span></a>
        """
        tags = []
        
        # Find all badge links with /tag/ href
        tag_links = soup.find_all('a', href=re.compile(r'^/tag/'))
        
        for link in tag_links:
            # Get the tag from href or from badge label
            href = link.get('href', '')
            tag_name = href.replace('/tag/', '')
            
            # Try to get from badge label for cleaner text
            badge_label = link.find('span', class_=re.compile(r'Badge-label'))
            if badge_label:
                tag_name = badge_label.get_text(strip=True)
            
            if tag_name and tag_name not in tags:
                tags.append(tag_name)
        
        # Limit to 15 tags
        return tags[:15]
    
    def _extract_trigger_words(self, soup):
        """
        Extract trigger/trained words from page
        Look for section with "Trained Words" or similar heading
        """
        trigger_words = []
        
        # Look for text containing "trained words" or "trigger words"
        trigger_section = soup.find(text=re.compile(r'(trained|trigger|activation)\s+(words?|text)', re.I))
        
        if trigger_section:
            # Find parent container
            parent = trigger_section.find_parent()
            if parent:
                # Look for code/badge elements near it
                codes = parent.find_all(['code', 'span'], limit=20)
                for code in codes:
                    word = code.get_text(strip=True)
                    if word and len(word) < 50 and word not in trigger_words:
                        trigger_words.append(word)
        
        # Also check for badge elements that might contain trigger words
        # Sometimes they're in a list or flex container
        badge_containers = soup.find_all('div', class_=re.compile(r'(trigger|trained|words)', re.I))
        for container in badge_containers:
            badges = container.find_all('span', class_=re.compile(r'Badge'))
            for badge in badges:
                word = badge.get_text(strip=True)
                if word and len(word) < 50 and word not in trigger_words:
                    trigger_words.append(word)
        
        return trigger_words[:10]  # Limit to 10 trigger words
    
    def _extract_versions(self, soup, model_id):
        """
        Extract all available versions from page
        Version buttons: <button><span class="mantine-Button-label"><div>Version Name</div></span></button>
        """
        versions = []
        
        # Find all version buttons - they have data like "Illustrious v8.0", "v7.0" etc
        button_labels = soup.find_all('span', class_=re.compile(r'Button-label'))
        
        for label in button_labels:
            text = label.get_text(strip=True)
            
            # Check if this looks like a version (contains "v" and numbers or "Illustrious")
            if re.search(r'(v\d+\.\d+|version\s+\d)', text, re.I) or 'Illustrious' in text:
                # This is probably a version button
                # Try to extract version ID from nearby links or data attributes
                parent_button = label.find_parent('button')
                
                if parent_button:
                    # Version name is the text
                    version_name = text
                    
                    # Try to find version ID from onclick or data attributes
                    # For now, we'll mark it as unknown - user will need to match manually
                    version_data = {
                        'versionId': None,  # Will be populated later if we find AIR codes
                        'name': version_name,
                        'baseModel': 'Unknown',
                        'downloadUrl': f"https://civitai.com/models/{model_id}"
                    }
                    
                    versions.append(version_data)
        
        # Try to find AIR codes which contain model and version IDs
        # Format: civitai:453428@2311163
        air_codes = soup.find_all('code', class_=re.compile(r'Code-root'))
        
        current_version_id = None
        for i, code in enumerate(air_codes):
            text = code.get_text(strip=True)
            
            # Check if this is the version ID part (comes after @)
            if text.isdigit() and len(text) > 5:
                # Check if previous code was model ID
                if i > 0:
                    prev_code = air_codes[i-1].get_text(strip=True)
                    if prev_code.isdigit():
                        # This is the version ID
                        current_version_id = text
                        break
        
        # If we found the current version ID from AIR, update the first version
        if current_version_id and versions:
            versions[0]['versionId'] = current_version_id
            versions[0]['status'] = 'owned'
        
        # Try to extract base model from details table
        base_model = self._extract_base_model_from_table(soup)
        if base_model:
            for version in versions:
                version['baseModel'] = base_model
        
        return versions
    
    def _extract_base_model_from_table(self, soup):
        """
        Extract base model from details table
        Table row: <td>Base Model</td><td>Illustrious</td>
        """
        # Find all table cells
        cells = soup.find_all('td')
        
        for i, cell in enumerate(cells):
            if 'base model' in cell.get_text(strip=True).lower():
                # Next cell should have the base model name
                if i + 1 < len(cells):
                    base_model = cells[i + 1].get_text(strip=True)
                    # Clean up any extra text
                    return base_model.split('\n')[0].strip()
        
        return "Unknown"
    
    def detect_version_groups(self, models_dict):
        """
        Detect which models belong to the same version group
        based on matching civitaiModelId
        
        Returns a dict of modelId -> list of paths
        """
        version_groups = {}
        
        for path, model in models_dict.items():
            model_id = model.get('civitaiModelId')
            if model_id:
                if model_id not in version_groups:
                    version_groups[model_id] = []
                version_groups[model_id].append(path)
        
        # Filter to only groups with 2+ models
        return {k: v for k, v in version_groups.items() if len(v) > 1}
    
    def link_version_group(self, models_dict, model_id, paths):
        """
        Link multiple models as versions of the same model family
        
        Args:
            models_dict: The models dictionary to modify
            model_id: The CivitAI model ID
            paths: List of model paths to link
        """
        group_id = f"civitai_{model_id}"
        
        for path in paths:
            if path in models_dict:
                model = models_dict[path]
                model['versionGroup'] = group_id
                
                # Add all other paths as related versions
                model['relatedVersions'] = [p for p in paths if p != path]
        
        print(f"🔗 Linked {len(paths)} models in version group {model_id}")
        self.log_activity('Versions Linked', f"{len(paths)} models", 'success', 
                         f"Group: {model_id}")


# Singleton instance
_civitai_service = None

def get_civitai_service():
    """Get or create the CivitAI service singleton"""
    global _civitai_service
    if _civitai_service is None:
        _civitai_service = CivitAIService()
    return _civitai_service