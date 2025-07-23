#!/usr/bin/env python3
"""
Quick test script for the file scanner
Run this from your project directory to test the scanner
"""

import sys
import os
sys.path.append('.')

from services.file_scanner import FileScanner, quick_scan

def test_scanner():
    # Test with your actual ComfyUI models directory
    test_directory = input("Enter your ComfyUI models directory path: ").strip()
    
    if not os.path.exists(test_directory):
        print(f"❌ Directory not found: {test_directory}")
        return
    
    print(f"🔍 Testing scanner on: {test_directory}")
    
    try:
        # Use quick_scan for testing
        models, stats = quick_scan(test_directory)
        
        print(f"\n✅ Scan Results:")
        print(f"📊 Total models found: {stats['total_models']}")
        print(f"📝 Models with notes: {stats['with_notes']}")
        print(f"💾 Total size: {stats['total_size_gb']:.2f} GB")
        
        print(f"\n📋 By type:")
        for model_type, count in stats['by_type'].items():
            print(f"   - {model_type}: {count}")
        
        if models:
            print(f"\n🔍 First few models:")
            for model in models[:3]:
                print(f"   - {model['name']} ({model['type']}, {model['size']})")
                if model['has_notes']:
                    note_preview = model['notes'][:100] + "..." if len(model['notes']) > 100 else model['notes']
                    print(f"     Notes: {note_preview}")
        
        return True
        
    except Exception as e:
        print(f"❌ Scanner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_scanner()