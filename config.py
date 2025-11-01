"""
Configuration settings for ComfyUI Model Explorer
"""
import os

# Base directory - where the app is running
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Models directory - can be overridden by environment variable
MODELS_DIR = os.getenv('MODELS_DIR', BASE_DIR)

# Database file location
DB_FILE = os.path.join(MODELS_DIR, 'modeldb.json')

# Images directory location
IMAGES_DIR = os.path.join(MODELS_DIR, 'images')

# Backup directory location
BACKUP_DIR = os.path.join(MODELS_DIR, 'db', 'backups')

# Backup configuration
MAX_BACKUPS = 10  # Keep only the last 10 backups

# Flask configuration
FLASK_CONFIG = {
    'host': '0.0.0.0',
    'port': 5000,
    'debug': True,
    'use_reloader': True
}

# Allowed file extensions for media uploads
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}

# Upload configuration
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size