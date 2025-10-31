"""
Database operations for model metadata
"""
import json
import os
from datetime import datetime
from config import DB_FILE


def load_db():
    """Load database from JSON file"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # Return empty database if file doesn't exist
            return {
                "version": "1.0.0",
                "models": {}
            }
    except Exception as e:
        print(f"Error loading database: {e}")
        return {
            "version": "1.0.0",
            "models": {}
        }


def save_db(data):
    """Save database to JSON file"""
    try:
        # Create backup before saving
        if os.path.exists(DB_FILE):
            backup_file = f"{DB_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(backup_data)
            print(f"✅ Created backup: {backup_file}")
        
        # Save new data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved database: {len(data.get('models', {}))} models")
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False