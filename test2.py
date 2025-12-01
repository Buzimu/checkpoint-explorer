"""
Version Linking Diagnostic Tool
Analyzes why two specific models were linked together
"""
import json
import sys


def load_database(db_path='modeldb.json'):
    """Load the database"""
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Database not found: {db_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return None


def analyze_link(db, path1, path2):
    """
    Analyze why two models are linked
    
    Args:
        db: Database dictionary
        path1: First model path
        path2: Second model path
    """
    print("\n" + "=" * 80)
    print("🔍 VERSION LINKING DIAGNOSTIC")
    print("=" * 80)
    
    # Get models
    model1 = db['models'].get(path1)
    model2 = db['models'].get(path2)
    
    if not model1:
        print(f"\n❌ Model 1 not found: {path1}")
        return
    if not model2:
        print(f"\n❌ Model 2 not found: {path2}")
        return
    
    print(f"\n📋 MODEL 1: {model1.get('name', 'Unknown')}")
    print(f"   Path: {path1}")
    print(f"\n📋 MODEL 2: {model2.get('name', 'Unknown')}")
    print(f"   Path: {path2}")
    
    # Check if they're actually linked
    print("\n" + "-" * 80)
    print("🔗 LINK STATUS")
    print("-" * 80)
    
    related1 = model1.get('relatedVersions', [])
    related2 = model2.get('relatedVersions', [])
    
    if path2 in related1:
        print(f"✅ Model 1 → Model 2: LINKED")
    else:
        print(f"❌ Model 1 → Model 2: NOT LINKED")
    
    if path1 in related2:
        print(f"✅ Model 2 → Model 1: LINKED")
    else:
        print(f"❌ Model 2 → Model 1: NOT LINKED")
    
    if path2 not in related1 and path1 not in related2:
        print("\n⚠️  These models are NOT linked to each other!")
        return
    
    # Analyze WHY they're linked
    print("\n" + "-" * 80)
    print("🔍 ANALYSIS - Why They Were Linked")
    print("-" * 80)
    
    matches = []
    
    # Check CivitAI Model ID
    print("\n1️⃣ CivitAI Model ID Check:")
    model_id_1 = model1.get('civitaiModelId')
    model_id_2 = model2.get('civitaiModelId')
    
    print(f"   Model 1: {model_id_1 or 'None'}")
    print(f"   Model 2: {model_id_2 or 'None'}")
    
    if model_id_1 and model_id_2 and model_id_1 == model_id_2:
        print(f"   ✅ MATCH! Same CivitAI Model ID: {model_id_1}")
        matches.append(('CivitAI ID', model_id_1))
    else:
        print("   ❌ Different or missing CivitAI IDs")
    
    # Check file sizes
    print("\n2️⃣ File Size Check:")
    size1 = model1.get('fileSize') or model1.get('_fileSize', 0)
    size2 = model2.get('fileSize') or model2.get('_fileSize', 0)
    
    print(f"   Model 1: {format_size(size1)} ({size1:,} bytes)")
    print(f"   Model 2: {format_size(size2)} ({size2:,} bytes)")
    
    if size1 > 0 and size2 > 0:
        # Calculate percentage difference
        diff_bytes = abs(size2 - size1)
        diff_pct = diff_bytes / size1 if size1 > 0 else 0
        
        print(f"   Difference: {format_size(diff_bytes)} ({diff_pct * 100:.2f}%)")
        
        if diff_pct <= 0.05:  # 5% tolerance
            print(f"   ✅ MATCH! File sizes within 5% tolerance")
            matches.append(('File Size', f'{diff_pct * 100:.2f}% difference'))
        else:
            print(f"   ❌ File sizes differ by more than 5%")
    else:
        print("   ⚠️  Missing file size data")
    
    # Check file hashes
    print("\n3️⃣ File Hash Check:")
    hash1 = model1.get('fileHash')
    hash2 = model2.get('fileHash')
    
    if hash1 and hash2:
        print(f"   Model 1: {hash1}")
        print(f"   Model 2: {hash2}")
        
        if hash1 == hash2:
            print(f"   ⚠️  SAME HASH! These are identical files!")
            matches.append(('File Hash', 'Identical files'))
        else:
            print("   ✅ Different hashes (different files)")
    else:
        print("   ⚠️  Missing hash data")
    
    # Check variant hashes
    print("\n4️⃣ Variant Hash Check:")
    variants1 = model1.get('variants', {})
    variants2 = model2.get('variants', {})
    
    if variants1 or variants2:
        print(f"   Model 1 has variants: {bool(variants1)}")
        print(f"   Model 2 has variants: {bool(variants2)}")
        
        if variants1:
            print(f"     High: {variants1.get('high', 'N/A')}")
            print(f"     Low: {variants1.get('low', 'N/A')}")
            print(f"     High Hash: {variants1.get('highHash', 'N/A')}")
            print(f"     Low Hash: {variants1.get('lowHash', 'N/A')}")
        
        if variants2:
            print(f"     High: {variants2.get('high', 'N/A')}")
            print(f"     Low: {variants2.get('low', 'N/A')}")
            print(f"     High Hash: {variants2.get('highHash', 'N/A')}")
            print(f"     Low Hash: {variants2.get('lowHash', 'N/A')}")
    else:
        print("   No variant data")
    
    # Check names
    print("\n5️⃣ Name Pattern Check:")
    name1 = model1.get('name', '')
    name2 = model2.get('name', '')
    
    print(f"   Model 1: {name1}")
    print(f"   Model 2: {name2}")
    
    # Extract base names
    base1 = extract_base_name(name1)
    base2 = extract_base_name(name2)
    
    print(f"   Base 1: {base1}")
    print(f"   Base 2: {base2}")
    
    if base1 and base2 and base1 == base2:
        print(f"   ⚠️  MATCH! Similar base names: {base1}")
        print(f"   (Name matching may have been enabled)")
        matches.append(('Name Pattern', base1))
    else:
        print("   ❌ Different base names")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    if matches:
        print(f"\n✅ Found {len(matches)} matching criteria:")
        for i, (method, detail) in enumerate(matches, 1):
            print(f"   {i}. {method}: {detail}")
        
        print("\n💡 LIKELY REASON FOR LINKING:")
        if any(m[0] == 'CivitAI ID' for m in matches):
            print("   → CivitAI Model ID match (most reliable)")
        elif any(m[0] == 'File Size' for m in matches):
            print("   → File size similarity (fallback method)")
        elif any(m[0] == 'Name Pattern' for m in matches):
            print("   → Name pattern match (least reliable, may be false positive)")
    else:
        print("\n❌ NO MATCHING CRITERIA FOUND!")
        print("   This is unexpected. These models should not be linked.")
        print("   Possible causes:")
        print("   - Database corruption")
        print("   - Manual editing")
        print("   - Bug in linking algorithm")
    
    # Additional context
    print("\n" + "-" * 80)
    print("📋 ADDITIONAL INFORMATION")
    print("-" * 80)
    
    print(f"\nModel 1 Type: {model1.get('modelType', 'unknown')}")
    print(f"Model 2 Type: {model2.get('modelType', 'unknown')}")
    
    print(f"\nModel 1 Base: {model1.get('baseModel', 'unknown')}")
    print(f"Model 2 Base: {model2.get('baseModel', 'unknown')}")
    
    print(f"\nModel 1 File Type: {model1.get('fileType', 'unknown')}")
    print(f"Model 2 File Type: {model2.get('fileType', 'unknown')}")
    
    print("\n" + "=" * 80)


def extract_base_name(name):
    """Extract base name by removing version indicators"""
    import re
    
    name = name.lower()
    
    patterns = [
        r'\s+v\d+(\.\d+)*',
        r'\s+version\s+\d+',
        r'\s+-\s+\w+$',
        r'\s+\(.*?\)',
        r'\s+dev$',
        r'\s+schnell$',
        r'\s+turbo$',
        r'\s+\d+$',
    ]
    
    for pattern in patterns:
        name = re.sub(pattern, '', name)
    
    name = ' '.join(name.split())
    return name if len(name) > 2 else None


def format_size(bytes_val):
    """Format bytes as human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def find_all_links(db, path):
    """Find all models linked to a specific path"""
    model = db['models'].get(path)
    if not model:
        print(f"❌ Model not found: {path}")
        return
    
    related = model.get('relatedVersions', [])
    
    print(f"\n🔗 ALL LINKS for: {model.get('name', 'Unknown')}")
    print(f"   Path: {path}")
    print(f"\n   Linked to {len(related)} model(s):")
    
    for i, rel_path in enumerate(related, 1):
        rel_model = db['models'].get(rel_path)
        if rel_model:
            print(f"   {i}. {rel_model.get('name', 'Unknown')}")
            print(f"      {rel_path}")
        else:
            print(f"   {i}. ⚠️  Missing model: {rel_path}")


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     Version Linking Diagnostic Tool                         ║
║                                                              ║
║  Analyzes why two models were linked together                ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python diagnose_links.py <model_path>")
        print("     → Shows all links for a model")
        print()
        print("  python diagnose_links.py <model_path_1> <model_path_2>")
        print("     → Analyzes why two models are linked")
        print()
        print("Example:")
        print("  python diagnose_links.py 'loras/my-model.safetensors'")
        print("  python diagnose_links.py 'loras/model-a.safetensors' 'loras/model-b.safetensors'")
        return
    
    # Load database
    db = load_database()
    if not db:
        return
    
    if len(sys.argv) == 2:
        # Show all links for one model
        find_all_links(db, sys.argv[1])
    elif len(sys.argv) == 3:
        # Analyze link between two models
        analyze_link(db, sys.argv[1], sys.argv[2])
    else:
        print("❌ Too many arguments. Provide 1 or 2 model paths.")


if __name__ == '__main__':
    main()