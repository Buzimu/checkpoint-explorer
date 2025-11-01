"""
Database operations for model metadata
"""
import json
import os
from datetime import datetime
from pathlib import Path
from config import DB_FILE, BACKUP_DIR, MAX_BACKUPS


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


def rotate_backups():
    """
    Remove old backups, keeping only the MAX_BACKUPS most recent ones
    """
    try:
        if not os.path.exists(BACKUP_DIR):
            return
        
        # Get all backup files sorted by modification time (newest first)
        backup_files = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith('modeldb_') and filename.endswith('.json'):
                filepath = os.path.join(BACKUP_DIR, filename)
                backup_files.append((filepath, os.path.getmtime(filepath)))
        
        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x[1], reverse=True)
        
        # Remove old backups beyond MAX_BACKUPS
        if len(backup_files) > MAX_BACKUPS:
            for filepath, _ in backup_files[MAX_BACKUPS:]:
                try:
                    os.remove(filepath)
                    print(f"🗑️  Removed old backup: {os.path.basename(filepath)}")
                except Exception as e:
                    print(f"⚠️  Failed to remove backup {filepath}: {e}")
    
    except Exception as e:
        print(f"⚠️  Error during backup rotation: {e}")


def save_db(data):
    """Save database to JSON file with automatic backup rotation"""
    try:
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Create backup before saving (if database exists)
        if os.path.exists(DB_FILE):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"modeldb_{timestamp}.json"
            backup_path = os.path.join(BACKUP_DIR, backup_filename)
            
            # Copy current database to backup
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                backup_data = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(backup_data)
            
            print(f"✅ Created backup: db/backups/{backup_filename}")
            
            # Rotate old backups
            rotate_backups()
        
        # Save new data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved database: {len(data.get('models', {}))} models")
        return True
    
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False


def get_backup_info():
    """
    Get information about existing backups
    
    Returns:
        List of tuples: (filename, size, timestamp)
    """
    try:
        if not os.path.exists(BACKUP_DIR):
            return []
        
        backups = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith('modeldb_') and filename.endswith('.json'):
                filepath = os.path.join(BACKUP_DIR, filename)
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'timestamp': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    'mtime': stat.st_mtime
                })
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x['mtime'], reverse=True)
        return backups
    
    except Exception as e:
        print(f"⚠️  Error getting backup info: {e}")
        return []


def restore_from_backup(backup_filename):
    """
    Restore database from a specific backup file
    
    Args:
        backup_filename: Name of the backup file to restore from
        
    Returns:
        True if successful, False otherwise
    """
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            print(f"❌ Backup file not found: {backup_filename}")
            return False
        
        # Create a safety backup of current database before restoring
        if os.path.exists(DB_FILE):
            safety_backup = os.path.join(BACKUP_DIR, f"modeldb_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                safety_data = f.read()
            with open(safety_backup, 'w', encoding='utf-8') as f:
                f.write(safety_data)
            print(f"✅ Created safety backup: {os.path.basename(safety_backup)}")
        
        # Restore from backup
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = f.read()
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            f.write(backup_data)
        
        print(f"✅ Restored database from: {backup_filename}")
        return True
    
    except Exception as e:
        print(f"❌ Error restoring from backup: {e}")
        return False