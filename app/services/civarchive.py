"""
CivArchive integration service for model URL recovery
Provides hash-based search functionality to find archived model pages
"""
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time


class CivArchiveService:
    """
    Service for interacting with CivArchive (or similar archive service)
    Used for self-healing missing URLs by searching for models by hash
    """
    
    def __init__(self, base_url="https://civarchive.com"):
        """
        Initialize the CivArchive service
        
        Args:
            base_url: Base URL for the archive service (configurable for mirrors/alternatives)
        """
        self.base_url = base_url
        self.rate_limit_delay = 5  # 5 seconds between requests (be respectful)
        self.last_request_time = None
        self.timeout = 30  # 30 second timeout for requests
    
    def wait_for_rate_limit(self):
        """Wait if necessary to respect rate limit"""
        if not self.last_request_time:
            return
        
        elapsed = (datetime.now() - self.last_request_time).total_seconds()
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            print(f"⏳ Archive rate limit: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
    
    def search_by_hash(self, file_hash):
        """
        Search the archive for a model by its SHA256 hash
        
        Args:
            file_hash: SHA256 hash of the model file (64 characters)
        
        Returns:
            dict: Search result with the following structure:
            {
                'found': bool,
                'hash': str,
                'results': [
                    {
                        'source': str,  # 'civitai', 'huggingface', 'tensorart', etc.
                        'status': str,  # 'live', 'deleted', 'unknown'
                        'url': str,     # Original URL
                        'archiveUrl': str,  # URL to archived snapshot
                        'modelName': str,
                        'archivedDate': str,
                        'metadata': dict
                    }
                ],
                'searchedAt': str
            }
        """
        try:
            # Validate hash format
            if not re.match(r'^[A-Fa-f0-9]{64}$', file_hash):
                raise ValueError(f"Invalid SHA256 hash format: {file_hash}")
            
            # Wait for rate limit
            self.wait_for_rate_limit()
            
            # Build API URL - CivArchive has an API at /api/sha256/HASH
            api_url = f"{self.base_url}/api/sha256/{file_hash.upper()}"
            print(f"🔍 Searching archive API for hash: {file_hash[:16]}...")
            print(f"   URL: {api_url}")
            
            # Make request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(api_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Update rate limit timestamp
            self.last_request_time = datetime.now()
            
            # Parse the JSON response
            json_data = response.json()
            
            # Parse search results from JSON
            results = self._parse_api_response(json_data, file_hash)
            
            search_result = {
                'found': len(results) > 0,
                'hash': file_hash,
                'results': results,
                'searchedAt': datetime.now().isoformat()
            }
            
            if results:
                print(f"✅ Found {len(results)} result(s) in archive")
                for result in results:
                    print(f"   - {result['source']}: {result['modelName']} ({result['status']})")
            else:
                print(f"❌ No results found in archive")
            
            return search_result
            
        except requests.Timeout:
            print(f"⏱️  Archive search timed out after {self.timeout} seconds")
            return {
                'found': False,
                'hash': file_hash,
                'results': [],
                'error': 'timeout',
                'searchedAt': datetime.now().isoformat()
            }
        except requests.RequestException as e:
            print(f"❌ Archive request failed: {e}")
            return {
                'found': False,
                'hash': file_hash,
                'results': [],
                'error': str(e),
                'searchedAt': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Archive search error: {e}")
            return {
                'found': False,
                'hash': file_hash,
                'results': [],
                'error': str(e),
                'searchedAt': datetime.now().isoformat()
            }
    
    def _parse_api_response(self, json_data, file_hash):
        """
        Parse the JSON response from the CivArchive API
        
        Expected structure:
        {
            "files": [...],  # Top-level file info
            "model": {
                "id": 1904334,
                "name": "Illustrij: Quill",
                "type": "Checkpoint",
                "deletedAt": null,
                "version": {
                    "id": 2155473,
                    "files": [{
                        "sha256": "...",
                        ...
                    }],
                    "mirrors": [...]
                }
                ...
            }
        }
        """
        results = []
        
        try:
            # Extract model info
            model = json_data.get('model', {})
            if not model:
                print("   ⚠️  No model data in response")
                return results
                
            model_id = model.get('id')
            model_name = model.get('name', 'Unknown')
            model_type = model.get('type', 'Unknown')
            deleted_at = model.get('deletedAt')
            
            # Get the version info (nested under model)
            version_data = model.get('version', {})
            version_id = version_data.get('id')
            version_name = version_data.get('name', '')
            
            # Check version files for hash match
            hash_match = False
            version_files = version_data.get('files', [])
            for file in version_files:
                file_sha256 = file.get('sha256', '').lower()
                if file_sha256 == file_hash.lower():
                    hash_match = True
                    print(f"   ✅ Hash match found in version files!")
                    break
            
            # Build result if we have model info
            if model_id:
                # Construct CivitAI URL
                civitai_url = f"https://civitai.com/models/{model_id}"
                if version_id:
                    civitai_url += f"?modelVersionId={version_id}"
                
                result = {
                    'source': 'civitai',
                    'status': 'deleted' if deleted_at else 'live',
                    'url': civitai_url,
                    'archiveUrl': f"{self.base_url}/models/{model_id}",
                    'modelName': model_name,
                    'modelType': model_type,
                    'modelId': str(model_id),
                    'versionId': str(version_id) if version_id else None,
                    'versionName': version_name,
                    'archivedDate': version_data.get('createdAt', ''),
                    'hashMatch': hash_match,
                    'metadata': {
                        'deletedAt': deleted_at,
                        'files': version_files,
                    }
                }
                
                results.append(result)
                print(f"   ✅ Added CivitAI result: {model_name} (ID: {model_id})")
                    
            # Also check for other platform mirrors
            mirrors = version_data.get('mirrors', [])
            for mirror in mirrors:
                mirror_platform = mirror.get('platform', 'unknown')
                mirror_url = mirror.get('platform_url', '')
                mirror_name = mirror.get('name', model_name)
                
                if mirror_url and mirror_platform != 'civitai':  # Don't duplicate civitai
                    results.append({
                        'source': mirror_platform,
                        'status': 'live',
                        'url': mirror_url,
                        'archiveUrl': f"{self.base_url}{mirror.get('href', '')}",
                        'modelName': mirror_name,
                        'modelType': model_type,
                        'modelId': mirror.get('id', ''),
                        'versionId': mirror.get('version_id', ''),
                        'versionName': mirror.get('version_name', ''),
                        'archivedDate': '',
                        'hashMatch': False,  # Mirrors don't have hash info
                        'metadata': {
                            'platform': mirror_platform,
                        }
                    })
                    print(f"   ✅ Added mirror result: {mirror_platform}")
            
            print(f"   📦 Total parsed results: {len(results)}")
            
        except Exception as e:
            print(f"   ⚠️  Error parsing API response: {e}")
            import traceback
            traceback.print_exc()
        
        return results
    
    def _parse_search_results(self, soup, file_hash):
        """
        Parse search results from the HTML page
        
        NOTE: This is a flexible parser that will need to be updated
        once we confirm the actual HTML structure of civarchive.org
        
        This implementation includes multiple parsing strategies:
        1. Look for common patterns
        2. Extract JSON if available
        3. Parse HTML elements with various selectors
        """
        results = []
        
        # Strategy 1: Look for Next.js JSON data (like CivitAI)
        json_results = self._try_parse_json_data(soup)
        if json_results:
            return json_results
        
        # Strategy 2: Look for result containers with common class names
        html_results = self._try_parse_html_results(soup)
        if html_results:
            return html_results
        
        # Strategy 3: Look for any links to civitai.com or other platforms
        link_results = self._try_parse_from_links(soup)
        if link_results:
            return link_results
        
        # If we get here, we couldn't parse anything
        # Save the HTML for manual inspection
        self._save_html_for_debug(soup, file_hash)
        
        return results
    
    def _try_parse_json_data(self, soup):
        """Try to extract results from embedded JSON (Next.js, React, etc.)"""
        results = []
        
        # Look for Next.js data
        next_data = soup.find('script', {'id': '__NEXT_DATA__'})
        if next_data and next_data.string:
            try:
                import json
                data = json.loads(next_data.string)
                # TODO: Parse the actual structure once we know it
                # This is a placeholder that shows the concept
                print("   📦 Found Next.js JSON data")
            except:
                pass
        
        # Look for other JSON scripts
        json_scripts = soup.find_all('script', type='application/json')
        for script in json_scripts:
            if script.string:
                try:
                    import json
                    data = json.loads(script.string)
                    # TODO: Parse based on actual structure
                    print(f"   📦 Found JSON data: {len(script.string)} bytes")
                except:
                    pass
        
        return results
    
    def _try_parse_html_results(self, soup):
        """Try to parse results from HTML structure"""
        results = []
        
        # Common class name patterns for result containers
        result_selectors = [
            ('div', 'result-item'),
            ('div', 'search-result'),
            ('article', 'model-card'),
            ('div', 'model-item'),
            ('div', lambda x: x and 'result' in x.lower() if x else False),
        ]
        
        for tag, class_pattern in result_selectors:
            containers = soup.find_all(tag, class_=class_pattern)
            if containers:
                print(f"   🎯 Found {len(containers)} result containers with <{tag} class='{class_pattern}'>")
                for container in containers:
                    result = self._parse_result_container(container)
                    if result:
                        results.append(result)
                break  # Use first successful selector
        
        return results
    
    def _parse_result_container(self, container):
        """Parse a single result container"""
        result = {
            'source': 'unknown',
            'status': 'unknown',
            'url': None,
            'archiveUrl': None,
            'modelName': 'Unknown',
            'archivedDate': None,
            'metadata': {}
        }
        
        # Try to find model name (look in various common places)
        name_selectors = [
            container.find('h2'),
            container.find('h3'),
            container.find(class_=lambda x: x and 'name' in x.lower() if x else False),
            container.find(class_=lambda x: x and 'title' in x.lower() if x else False),
        ]
        for element in name_selectors:
            if element and element.get_text(strip=True):
                result['modelName'] = element.get_text(strip=True)
                break
        
        # Try to find links
        links = container.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            
            # CivitAI link
            if 'civitai.com' in href:
                result['url'] = href if href.startswith('http') else f"https://{href}"
                result['source'] = 'civitai'
            
            # HuggingFace link
            elif 'huggingface.co' in href:
                result['url'] = href if href.startswith('http') else f"https://{href}"
                result['source'] = 'huggingface'
            
            # Archive/snapshot link
            elif 'snapshot' in href or 'archive' in href:
                result['archiveUrl'] = href if href.startswith('http') else f"{self.base_url}{href}"
        
        # Try to find status badge
        status_selectors = [
            container.find(class_=lambda x: x and 'status' in x.lower() if x else False),
            container.find(class_=lambda x: x and 'badge' in x.lower() if x else False),
        ]
        for element in status_selectors:
            if element:
                status_text = element.get_text(strip=True).lower()
                if 'live' in status_text or 'active' in status_text:
                    result['status'] = 'live'
                elif 'deleted' in status_text or 'removed' in status_text:
                    result['status'] = 'deleted'
                break
        
        # Try to find archived date
        date_selectors = [
            container.find(class_=lambda x: x and 'date' in x.lower() if x else False),
            container.find('time'),
        ]
        for element in date_selectors:
            if element:
                result['archivedDate'] = element.get_text(strip=True)
                # Also try datetime attribute
                if element.get('datetime'):
                    result['archivedDate'] = element.get('datetime')
                break
        
        # Only return if we found at least a URL
        return result if result['url'] or result['archiveUrl'] else None
    
    def _try_parse_from_links(self, soup):
        """Fallback: just look for any relevant links on the page"""
        results = []
        
        # Find all civitai links
        civitai_links = soup.find_all('a', href=lambda x: x and 'civitai.com' in x)
        for link in civitai_links:
            result = {
                'source': 'civitai',
                'status': 'unknown',
                'url': link.get('href'),
                'archiveUrl': None,
                'modelName': link.get_text(strip=True) or 'Unknown',
                'archivedDate': None,
                'metadata': {}
            }
            results.append(result)
        
        # Find all huggingface links
        hf_links = soup.find_all('a', href=lambda x: x and 'huggingface.co' in x)
        for link in hf_links:
            result = {
                'source': 'huggingface',
                'status': 'unknown',
                'url': link.get('href'),
                'archiveUrl': None,
                'modelName': link.get_text(strip=True) or 'Unknown',
                'archivedDate': None,
                'metadata': {}
            }
            results.append(result)
        
        if results:
            print(f"   🔗 Extracted {len(results)} results from links")
        
        return results
    
    def _save_html_for_debug(self, soup, file_hash):
        """Save HTML for manual inspection when parsing fails"""
        try:
            filename = f"archive_search_{file_hash[:16]}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            print(f"   💾 Saved HTML for debugging: {filename}")
            print(f"   ⚠️  Please inspect this file and update the parser accordingly")
        except Exception as e:
            print(f"   ⚠️  Could not save debug HTML: {e}")
    
    def get_archive_snapshot(self, snapshot_url):
        """
        Fetch and parse an archived snapshot page
        
        This allows us to extract model data from archived CivitAI pages
        even if the original page has been deleted
        
        Args:
            snapshot_url: URL to the archived snapshot
        
        Returns:
            dict: Parsed data from the archived page
        """
        try:
            self.wait_for_rate_limit()
            
            print(f"📸 Fetching archive snapshot...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = requests.get(snapshot_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            self.last_request_time = datetime.now()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try to extract the original URL from the archive banner
            original_url = self._extract_original_url(soup)
            
            # Try to parse the archived CivitAI content
            # (The archived page should look like a regular CivitAI page)
            # We can potentially reuse CivitAIService parsing logic here
            
            return {
                'success': True,
                'originalUrl': original_url,
                'html': str(soup),
                'fetchedAt': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Failed to fetch archive snapshot: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_original_url(self, soup):
        """Extract the original URL from an archive page banner"""
        # Common patterns for archive banners
        banner_selectors = [
            soup.find(class_=lambda x: x and 'archive-banner' in x.lower() if x else False),
            soup.find(class_=lambda x: x and 'original-url' in x.lower() if x else False),
            soup.find(id=lambda x: x and 'banner' in x.lower() if x else False),
        ]
        
        for banner in banner_selectors:
            if banner:
                # Look for links in the banner
                links = banner.find_all('a', href=lambda x: x and 'civitai.com' in x)
                if links:
                    return links[0].get('href')
        
        return None


# Global service instance
_civarchive_service = None

def get_civarchive_service(base_url="https://civarchive.com"):
    """Get or create the global CivArchive service instance"""
    global _civarchive_service
    if _civarchive_service is None:
        _civarchive_service = CivArchiveService(base_url)
    return _civarchive_service
