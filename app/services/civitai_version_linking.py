"""
CivitAI-Driven Version Linking
Links versions when CivitAI data is scraped, not as standalone operation
"""
from app.services.database import load_db, save_db


def link_versions_from_civitai_scrape(model_path, scraped_data):
    """
    Link versions based on CivitAI scrape results
    This runs automatically after successful CivitAI scrape
    
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
    
    if model_id:
        clean_conflicting_links(db, model_path, model_id)
        save_db(db)  # Save after cleanup
        db = load_db()  # Reload fresh copy
        current_model = db['models'][model_path]
    
    print(f"   Found {len(versions)} versions in CivitAI data")
    
    # Track matches
    confirmed_links = []  # Both have CivitAI links
    assumed_links = []    # One has link, other matched by size
    
    # Current model's version info
    current_file_size = current_model.get('fileSize') or current_model.get('_fileSize', 0)
    
    # Search for each version in local database
    for version in versions:
        version_id = version.get('id')
        version_name = version.get('name', 'Unknown')
        
        # Skip the current version (ourselves)
        if version_id == current_version_id:
            continue
        
        # Get file sizes for this version from CivitAI
        version_files = version.get('files', [])
        version_sizes = [f.get('sizeKB', 0) * 1024 for f in version_files if f.get('sizeKB')]
        
        if not version_sizes:
            print(f"   ⚠️  No file sizes for version: {version_name}")
            continue
        
        print(f"\n   Searching for: {version_name} (Version ID: {version_id})")
        print(f"      CivitAI sizes: {[format_size(s) for s in version_sizes]}")
        
        # TIER 1: Search for CONFIRMED match (same Model ID + Version ID)
        confirmed_match = find_confirmed_match(db, model_id, version_id)
        
        if confirmed_match:
            match_path = confirmed_match['path']
            print(f"      ✅ CONFIRMED: {confirmed_match['name']}")
            print(f"         Both models have CivitAI link")
            
            confirmed_links.append({
                'path': match_path,
                'name': confirmed_match['name'],
                'versionId': version_id,
                'versionName': version_name,
                'method': 'civitai_id'
            })
            continue
        
        # TIER 2: Search for ASSUMED match (file size within ±1%)
        assumed_match = find_assumed_match(
            db, 
            version_sizes, 
            exclude_path=model_path, 
            tolerance=0.01,
            current_model_id=model_id  # NEW: Pass current model's ID to prevent cross-family matches
        )
        
        if assumed_match:
            match_path = assumed_match['path']
            match_size = assumed_match['size']
            match_diff_pct = assumed_match['diff_pct']
            
            print(f"      🔍 ASSUMED: {assumed_match['name']}")
            print(f"         Matched by file size: {format_size(match_size)} ({match_diff_pct:.2f}% diff)")
            print(f"         ⚠️  This model doesn't have CivitAI link yet")
            
            assumed_links.append({
                'path': match_path,
                'name': assumed_match['name'],
                'versionId': version_id,
                'versionName': version_name,
                'method': 'file_size',
                'size': match_size,
                'diff_pct': match_diff_pct
            })
        else:
            print(f"      ❌ No match found")
    
    # Apply the links to database
    if confirmed_links or assumed_links:
        apply_version_links(db, model_path, confirmed_links, assumed_links)
        save_db(db)
        
        print(f"\n✅ Linking complete:")
        print(f"   Confirmed links: {len(confirmed_links)}")
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


def find_assumed_match(db, target_sizes, exclude_path=None, tolerance=0.01, current_model_id=None):
    """
    Find a model that matches by file size (within tolerance)
    This is an ASSUMED match - we think they're related but not confirmed
    
    Args:
        target_sizes: List of possible file sizes from CivitAI
        exclude_path: Path to exclude (ourselves)
        tolerance: Size difference tolerance (default 1%)
        current_model_id: Current model's CivitAI Model ID (to avoid cross-family matches)
    """
    best_match = None
    best_diff = float('inf')
    
    for path, model in db['models'].items():
        # Skip missing models and ourselves
        if path.startswith('_missing/') or path == exclude_path:
            continue
        
        # CRITICAL BUGFIX: If this model has a DIFFERENT CivitAI Model ID,
        # they are confirmed to be from different families - NEVER match them
        other_model_id = model.get('civitaiModelId')
        if other_model_id and current_model_id:
            if str(other_model_id) != str(current_model_id):
                # Confirmed different families - skip this model entirely
                continue
        
        # Skip models that already have CivitAI links to the SAME family
        # (those should have been found by confirmed match, not assumed)
        if other_model_id and current_model_id and str(other_model_id) == str(current_model_id):
            # Same family - should have been confirmed match
            # Skip to avoid duplicate linking
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
        
        # Check if related model has a DIFFERENT Model ID
        other_model_id = related_model.get('civitaiModelId')
        
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