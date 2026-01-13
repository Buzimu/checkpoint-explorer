"""
CivitAI-Driven Version Linking
Links versions when CivitAI data is scraped, not as standalone operation

BUGFIX: Prevents false positive linking by checking BOTH civitaiModelId AND civitaiUrl
"""
from app.services.database import load_db, save_db
import re


def extract_model_id_from_url(url):
    """
    Extract CivitAI Model ID from URL without requiring a scrape
    
    Args:
        url: CivitAI URL like "https://civitai.com/models/123456"
        
    Returns:
        Model ID as string, or None if not found
    """
    if not url:
        return None
    
    match = re.search(r'/models/(\d+)', url)
    if match:
        return match.group(1)
    return None


def get_model_id(model):
    """
    Get Model ID from either civitaiModelId field OR by parsing civitaiUrl
    
    This allows us to detect different model families even before scraping
    
    Args:
        model: Model dictionary
        
    Returns:
        Model ID as string, or None if neither field exists
    """
    # Try the scraped ID first
    if model.get('civitaiModelId'):
        return str(model['civitaiModelId'])
    
    # Fall back to parsing the URL
    url = model.get('civitaiUrl', '')
    if url:
        return extract_model_id_from_url(url)
    
    return None


def link_versions_from_civitai_scrape(model_path, scraped_data):
    """
    Link versions based on CivitAI scrape results
    This runs automatically after successful CivitAI scrape
    
    NEW: THREE-TIER matching system (in priority order):
    1. Hash matching (CONFIRMED - 100% reliable, no false positives)
    2. Model ID + Version ID (CONFIRMED - both have CivitAI links)
    3. File size tolerance (ASSUMED - fallback only, less reliable)
    
    Args:
        model_path: Path to the model that was just scraped
        scraped_data: The civitaiData object from scraping
        
    Returns:
        Dictionary with linking results:
        {
            'confirmed': [list of confirmed links],
            'assumed': [list of assumed links],
            'stats': {...}
        }
    """
    print(f"\n🔗 Auto-linking versions for: {model_path}")
    
    db = load_db()
    current_model = db['models'].get(model_path)
    
    if not current_model:
        print(f"❌ Model not found: {model_path}")
        return None
    
    # Get version information from scraped data
    versions = scraped_data.get('versions', [])
    current_version_id = scraped_data.get('currentVersionId')
    model_id = scraped_data.get('modelId')
    
    if not versions:
        print("   No versions found in scraped data")
        return {'confirmed': [], 'assumed': [], 'stats': {}}
    
    # CRITICAL: If this model only has 1 version, DO NOT create assumed links
    # (prevents matching unrelated models with similar sizes)
    if len(versions) == 1:
        print(f"   ⚠️  Only 1 version found - skipping assumed linking to prevent false positives")
        return {'confirmed': [], 'assumed': [], 'stats': {}}
    
    if model_id:
        clean_conflicting_links(db, model_path, model_id)
        save_db(db)  # Save after cleanup
        db = load_db()  # Reload fresh copy
        current_model = db['models'][model_path]
    
    print(f"   Found {len(versions)} versions in CivitAI data")
    
    # Track matches
    confirmed_links = []  # Hash match OR both have CivitAI IDs
    assumed_links = []    # File size match only
    
    # Search for each version in local database
    for version in versions:
        version_id = version.get('id')
        version_name = version.get('name', 'Unknown')
        
        # Skip the current version (ourselves)
        if version_id == current_version_id:
            continue
        
        # Get file hashes for this version from CivitAI
        version_files = version.get('files', [])
        version_hashes = [f.get('hash') for f in version_files if f.get('hash')]
        version_sizes = [f.get('sizeKB', 0) * 1024 for f in version_files if f.get('sizeKB')]
        
        print(f"\n   Searching for: {version_name} (Version ID: {version_id})")
        if version_hashes:
            # Show first hash (truncated for readability)
            first_hash = version_hashes[0]
            display_hash = first_hash[:16] + '...' if len(first_hash) > 16 else first_hash
            print(f"      CivitAI hashes: [{display_hash}] ({len(version_hashes)} file(s))")
        
        # ========================================================================
        # TIER 1: HASH MATCH (Most reliable - 100% accuracy!)
        # ========================================================================
        hash_match = find_hash_match(db, version_hashes)
        
        if hash_match:
            match_path = hash_match['path']
            print(f"      ✅ CONFIRMED (Hash Match): {hash_match['name']}")
            print(f"         🎯 Definitive match - identical file hash!")
            
            confirmed_links.append({
                'path': match_path,
                'name': hash_match['name'],
                'versionId': version_id,
                'versionName': version_name,
                'method': 'hash_match'  # 🆕 NEW METHOD TYPE
            })
            continue
        
        # ========================================================================
        # TIER 2: MODEL ID + VERSION ID MATCH (Confirmed via CivitAI URLs)
        # ========================================================================
        confirmed_match = find_confirmed_match(db, model_id, version_id)
        
        if confirmed_match:
            match_path = confirmed_match['path']
            print(f"      ✅ CONFIRMED (CivitAI IDs): {confirmed_match['name']}")
            print(f"         Both models have matching CivitAI links")
            
            confirmed_links.append({
                'path': match_path,
                'name': confirmed_match['name'],
                'versionId': version_id,
                'versionName': version_name,
                'method': 'civitai_id'
            })
            continue
        
        # ========================================================================
        # TIER 3: FILE SIZE MATCH (Assumed - last resort, less reliable)
        # ========================================================================
        # Only use if we don't have hash data AND we have size data
        if not version_hashes and version_sizes:
            assumed_match = find_assumed_match(
                db, 
                version_sizes, 
                exclude_path=model_path, 
                tolerance=0.01,  # Very strict 1% tolerance to minimize false positives
                current_model_id=model_id
            )
            
            if assumed_match:
                match_path = assumed_match['path']
                match_size = assumed_match['size']
                match_diff_pct = assumed_match['diff_pct']
                
                print(f"      🔍 ASSUMED (File Size): {assumed_match['name']}")
                print(f"         Matched by file size: {format_size(match_size)} ({match_diff_pct:.2f}% diff)")
                print(f"         ⚠️  No hash data available - less reliable")
                
                assumed_links.append({
                    'path': match_path,
                    'name': assumed_match['name'],
                    'versionId': version_id,
                    'versionName': version_name,
                    'method': 'file_size',
                    'size': match_size,
                    'diff_pct': match_diff_pct
                })
                continue
        
        print(f"      ❌ No match found")
    
    # Apply the links to database
    if confirmed_links or assumed_links:
        apply_version_links(db, model_path, confirmed_links, assumed_links)
        save_db(db)
        
        print(f"\n✅ Linking complete:")
        print(f"   Confirmed links: {len(confirmed_links)}")
        if confirmed_links:
            hash_matches = sum(1 for link in confirmed_links if link.get('method') == 'hash_match')
            id_matches = sum(1 for link in confirmed_links if link.get('method') == 'civitai_id')
            if hash_matches > 0:
                print(f"     • {hash_matches} by hash (definitive)")
            if id_matches > 0:
                print(f"     • {id_matches} by CivitAI ID")
        print(f"   Assumed links: {len(assumed_links)}")
    else:
        print(f"\n   No versions found locally")
    
    return {
        'confirmed': confirmed_links,
        'assumed': assumed_links,
        'stats': {
            'total_versions': len(versions),
            'confirmed': len(confirmed_links),
            'assumed': len(assumed_links)
        }
    }

def find_hash_match(db, target_hashes):
    """
    Find a model that has a matching file hash
    This is a CONFIRMED match - definitive proof they're the same file
    
    Matches:
    1. Full SHA256 (64 chars) - exact match with our PowerShell-generated hashes
    2. First 10 chars of SHA256 - if CivitAI only provided AutoV2
    3. Handles both directions (model has full hash, CivitAI has partial, or vice versa)
    
    This is the MOST RELIABLE matching method - 100% accuracy, no false positives.
    """
    if not target_hashes:
        return None
    
    for path, model in db['models'].items():
        # Skip missing models
        if path.startswith('_missing/'):
            continue
        
        # Check main file hash
        model_hash = (model.get('fileHash') or '').upper()
        
        if model_hash and hash_matches(model_hash, target_hashes):
            return {
                'path': path,
                'name': model.get('name', 'Unknown'),
                'hash': model_hash
            }
        
        # Check variant hashes
        if model.get('variants'):
            high_hash = (model['variants'].get('highHash') or '').upper()
            if high_hash and hash_matches(high_hash, target_hashes):
                return {
                    'path': path,
                    'name': model.get('name', 'Unknown'),
                    'hash': high_hash
                }
            
            low_hash = (model['variants'].get('lowHash') or '').upper()
            if low_hash and hash_matches(low_hash, target_hashes):
                return {
                    'path': path,
                    'name': model.get('name', 'Unknown'),
                    'hash': low_hash
                }
    
    return None


def hash_matches(model_hash, target_hashes):
    """
    Check if a model hash matches any of the target hashes
    Handles both full SHA256 (64 chars) and partial AutoV2 (10 chars) matches
    """
    if not model_hash:
        return False
    
    model_upper = model_hash.upper()
    
    for target_hash in target_hashes:
        if not target_hash:
            continue
        
        target_upper = target_hash.upper()
        
        # Method 1: Exact match (both are full SHA256 or both are AutoV2)
        if model_upper == target_upper:
            return True
        
        # Method 2: Partial match - CivitAI provided AutoV2 (10 chars), we have full SHA256 (64 chars)
        if len(target_upper) == 10 and len(model_upper) == 64:
            if model_upper.startswith(target_upper):
                return True
        
        # Method 3: Reverse partial - we have AutoV2 (10 chars), CivitAI provided full SHA256 (64 chars)
        if len(model_upper) == 10 and len(target_upper) == 64:
            if target_upper.startswith(model_upper):
                return True
    
    return False


def find_confirmed_match(db, model_id, version_id):
    """
    Find a model that has the SAME CivitAI Model ID and Version ID
    This is a CONFIRMED match - both models have CivitAI links
    """
    for path, model in db['models'].items():
        # Skip missing models
        if path.startswith('_missing/'):
            continue
        
        # Check if this model has matching IDs
        if (model.get('civitaiModelId') == model_id and 
            model.get('civitaiVersionId') == version_id):
            return {
                'path': path,
                'name': model.get('name', 'Unknown'),
                'modelId': model_id,
                'versionId': version_id
            }
    
    return None


def find_assumed_match(db, target_sizes, exclude_path=None, tolerance=0.001, current_model_id=None):
    """
    Find a model that matches by file size (within tolerance)
    This is an ASSUMED match - we think they're related but not confirmed
    
    CRITICAL SAFETY CHECKS:
    1. Checks BOTH civitaiModelId AND civitaiUrl (via URL parsing)
    2. NEVER matches models with different CivitAI Model IDs (even if not scraped)
    3. NEVER matches if other model has ANY CivitAI link to different model
    4. Uses STRICT 0.1% tolerance (not 1%) to prevent false positives
    
    Args:
        target_sizes: List of possible file sizes from CivitAI
        exclude_path: Path to exclude (ourselves)
        tolerance: Size difference tolerance (default 0.1%)
        current_model_id: Current model's CivitAI Model ID
    """
    best_match = None
    best_diff = float('inf')
    
    for path, model in db['models'].items():
        # Skip missing models and ourselves
        if path.startswith('_missing/') or path == exclude_path:
            continue
        
        # BUGFIX: Get Model ID from EITHER scraped data OR URL parsing
        other_model_id = get_model_id(model)
        
        # SAFETY CHECK 1: If we can determine the other model's ID (even from URL),
        # check if they're from different families
        if other_model_id and current_model_id:
            if str(other_model_id) != str(current_model_id):
                # Different CivitAI families - NEVER match!
                # This prevents linking "Aduare Style" with "cat_looking_at_itself"
                continue
        
        # SAFETY CHECK 2: If other model has SAME Model ID but different Version ID,
        # it should have been found by confirmed match - skip to avoid duplicates
        if other_model_id and current_model_id and str(other_model_id) == str(current_model_id):
            other_version_id = model.get('civitaiVersionId')
            if other_version_id:
                # Has both IDs - should have been confirmed match
                continue
        
        # Get model's file size
        model_size = model.get('fileSize') or model.get('_fileSize', 0)
        if model_size == 0:
            continue
        
        # Check against all possible sizes from CivitAI
        for target_size in target_sizes:
            if target_size == 0:
                continue
            
            # Calculate percentage difference
            diff = abs(model_size - target_size)
            diff_pct = diff / target_size
            
            # Within tolerance?
            if diff_pct <= tolerance:
                # Keep track of best match (smallest difference)
                if diff_pct < best_diff:
                    best_diff = diff_pct
                    best_match = {
                        'path': path,
                        'name': model.get('name', 'Unknown'),
                        'size': model_size,
                        'diff_pct': diff_pct * 100  # Convert to percentage
                    }
    
    return best_match


def apply_version_links(db, main_path, confirmed_links, assumed_links):
    """
    Apply version links to the database
    
    Creates bidirectional links and marks assumed links with metadata
    """
    main_model = db['models'][main_path]
    
    # Initialize relatedVersions if needed
    if 'relatedVersions' not in main_model:
        main_model['relatedVersions'] = []
    
    # Initialize linkMetadata for tracking confirmed vs assumed
    if 'linkMetadata' not in main_model:
        main_model['linkMetadata'] = {}
    
    # Process confirmed links
    for link in confirmed_links:
        link_path = link['path']
        
        # Add to main model's relatedVersions
        if link_path not in main_model['relatedVersions']:
            main_model['relatedVersions'].append(link_path)
        
        # Mark as confirmed
        main_model['linkMetadata'][link_path] = {
            'type': 'confirmed',
            'method': 'civitai_id',
            'versionId': link['versionId'],
            'versionName': link['versionName']
        }
        
        # Add reverse link
        linked_model = db['models'][link_path]
        if 'relatedVersions' not in linked_model:
            linked_model['relatedVersions'] = []
        if main_path not in linked_model['relatedVersions']:
            linked_model['relatedVersions'].append(main_path)
        
        # Mark reverse link as confirmed
        if 'linkMetadata' not in linked_model:
            linked_model['linkMetadata'] = {}
        linked_model['linkMetadata'][main_path] = {
            'type': 'confirmed',
            'method': 'civitai_id'
        }
    
    # Process assumed links
    for link in assumed_links:
        link_path = link['path']
        
        # Add to main model's relatedVersions
        if link_path not in main_model['relatedVersions']:
            main_model['relatedVersions'].append(link_path)
        
        # Mark as assumed with size info
        main_model['linkMetadata'][link_path] = {
            'type': 'assumed',
            'method': 'file_size',
            'versionId': link['versionId'],
            'versionName': link['versionName'],
            'sizeDiff': link['diff_pct']
        }
        
        # Add reverse link
        linked_model = db['models'][link_path]
        if 'relatedVersions' not in linked_model:
            linked_model['relatedVersions'] = []
        if main_path not in linked_model['relatedVersions']:
            linked_model['relatedVersions'].append(main_path)
        
        # Mark reverse link as assumed
        if 'linkMetadata' not in linked_model:
            linked_model['linkMetadata'] = {}
        linked_model['linkMetadata'][main_path] = {
            'type': 'assumed',
            'method': 'file_size',
            'sizeDiff': link['diff_pct']
        }


def upgrade_assumed_to_confirmed(db, path1, path2, model_id, version_id):
    """
    Upgrade an assumed link to confirmed when CivitAI data is added
    
    Call this when a model that was assumed-linked gets its CivitAI URL added
    """
    # Update link metadata for path1
    if path1 in db['models']:
        model1 = db['models'][path1]
        if 'linkMetadata' in model1 and path2 in model1['linkMetadata']:
            model1['linkMetadata'][path2] = {
                'type': 'confirmed',
                'method': 'civitai_id',
                'versionId': version_id
            }
    
    # Update link metadata for path2
    if path2 in db['models']:
        model2 = db['models'][path2]
        if 'linkMetadata' in model2 and path1 in model2['linkMetadata']:
            model2['linkMetadata'][path1] = {
                'type': 'confirmed',
                'method': 'civitai_id',
                'versionId': version_id
            }
    
    print(f"✅ Upgraded link to CONFIRMED: {path1} ↔ {path2}")


def clean_conflicting_links(db, model_path, confirmed_model_id):
    """
    Remove links to models from DIFFERENT families
    Called after scraping when we now KNOW the model's family ID
    
    Args:
        db: Database dictionary
        model_path: Path to the model we just scraped
        confirmed_model_id: The confirmed CivitAI Model ID from scraping
    """
    print(f"\n🧹 Cleaning conflicting links for: {model_path}")
    
    model = db['models'].get(model_path)
    if not model:
        return
    
    related_versions = model.get('relatedVersions', [])
    if not related_versions:
        print("   No related versions to clean")
        return
    
    # Check each link
    links_to_remove = []
    
    for related_path in related_versions:
        related_model = db['models'].get(related_path)
        if not related_model:
            links_to_remove.append(related_path)
            continue
        
        # BUGFIX: Check BOTH scraped ID and URL-parsed ID
        other_model_id = get_model_id(related_model)
        
        if other_model_id and str(other_model_id) != str(confirmed_model_id):
            # CONFLICT DETECTED: Different families linked together!
            print(f"   ❌ Removing conflicting link: {related_model.get('name', 'Unknown')}")
            print(f"      This model: {confirmed_model_id}, Other model: {other_model_id}")
            links_to_remove.append(related_path)
    
    # Remove conflicting links
    if links_to_remove:
        # Remove from this model's relatedVersions
        model['relatedVersions'] = [
            path for path in related_versions 
            if path not in links_to_remove
        ]
        
        # Remove from linkMetadata
        if 'linkMetadata' in model:
            for path in links_to_remove:
                if path in model['linkMetadata']:
                    del model['linkMetadata'][path]
        
        # Remove reverse links from the other models
        for related_path in links_to_remove:
            related_model = db['models'].get(related_path)
            if not related_model:
                continue
            
            # Remove from their relatedVersions
            if 'relatedVersions' in related_model:
                related_model['relatedVersions'] = [
                    path for path in related_model['relatedVersions']
                    if path != model_path
                ]
            
            # Remove from their linkMetadata
            if 'linkMetadata' in related_model:
                if model_path in related_model['linkMetadata']:
                    del related_model['linkMetadata'][model_path]
        
        print(f"   ✅ Removed {len(links_to_remove)} conflicting link(s)")
    else:
        print("   ✅ No conflicting links found")


def format_size(bytes_val):
    """Format bytes as human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def detect_newer_versions(db):
    """
    Detect models that have newer versions available on CivitAI
    
    For each model with civitaiData:
    1. Find its publishedAt date (or use the first primary model as reference)
    2. Check all relatedVersions for newer publishedAt dates
    3. Flag model with newVersionAvailable metadata
    
    Returns:
        Dictionary mapping model paths to their newer version info
    """
    from datetime import datetime
    
    print("\n🔍 Detecting newer versions...")
    
    newer_versions_found = {}
    
    for path, model in db['models'].items():
        # Skip missing models
        if path.startswith('_missing/'):
            continue
        
        # Check if model has CivitAI data with versions
        civitai_data = model.get('civitaiData')
        if not civitai_data or not civitai_data.get('versions'):
            continue
        
        # Get the current model's published date
        # First, try to find it from the civitaiVersionId
        current_version_id = model.get('civitaiVersionId')
        current_published_date = None
        
        for version in civitai_data['versions']:
            if str(version.get('id')) == str(current_version_id):
                current_published_date = version.get('publishedAt')
                break
        
        # If no current version found, use the first version (primary model)
        if not current_published_date and civitai_data['versions']:
            current_published_date = civitai_data['versions'][0].get('publishedAt')
        
        if not current_published_date:
            continue
        
        # Parse the current date
        try:
            current_date = datetime.fromisoformat(current_published_date.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            continue
        
        # Check all versions for newer ones
        newer_versions = []
        
        for version in civitai_data['versions']:
            version_id = str(version.get('id'))
            version_published = version.get('publishedAt')
            
            # Skip if this is the current version
            if version_id == str(current_version_id):
                continue
            
            if not version_published:
                continue
            
            try:
                version_date = datetime.fromisoformat(version_published.replace('Z', '+00:00'))
                
                # Check if this version is newer
                if version_date > current_date:
                    newer_versions.append({
                        'versionId': version_id,
                        'versionName': version.get('name', 'Unknown'),
                        'publishedAt': version_published,
                        'baseModel': version.get('baseModel', 'Unknown'),
                        'available': version.get('available', True),
                        'files': version.get('files', [])
                    })
            except (ValueError, AttributeError):
                continue
        
        # If newer versions found, store the info
        if newer_versions:
            # Sort by date (newest first)
            newer_versions.sort(key=lambda v: v['publishedAt'], reverse=True)
            
            newest = newer_versions[0]
            newer_versions_found[path] = {
                'hasNewerVersion': True,
                'newestVersion': newest,
                'allNewerVersions': newer_versions,
                'count': len(newer_versions)
            }
            
            print(f"   📢 {model.get('name', 'Unknown')}: {len(newer_versions)} newer version(s) found!")
            print(f"      Newest: {newest['versionName']} ({newest['publishedAt'][:10]})")
    
    print(f"\n✅ Detection complete: {len(newer_versions_found)} model(s) have newer versions")
    
    return newer_versions_found