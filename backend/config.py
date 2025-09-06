"""
Configuration management for ComfyUI Model Explorer
"""
import os
import json
from pathlib import Path
from typing import Dict, Any


class Config:
    """Base configuration"""
    
    # Application settings
    APP_NAME = 'ComfyUI Model Explorer'
    VERSION = '2.0.0'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'comfyui-model-explorer-secret-key-change-in-production'
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    FRONTEND_DIR = BASE_DIR / 'frontend'
    DATA_DIR = BASE_DIR / 'data'
    BACKUP_DIR = DATA_DIR / 'backups'
    TEMPLATES_DIR = DATA_DIR / 'templates'
    
    # Database
    DATABASE_PATH = DATA_DIR / 'models.db'
    
    # Flask settings
    TEMPLATE_FOLDER = str(FRONTEND_DIR)
    STATIC_FOLDER = str(FRONTEND_DIR)
    
    # File scanning
    SUPPORTED_EXTENSIONS = {
        '.safetensors': 'SafeTensors',
        '.ckpt': 'Checkpoint', 
        '.pt': 'PyTorch',
        '.pth': 'PyTorch',
        '.bin': 'Binary'
    }
    
    # Model type patterns for detection
    MODEL_TYPE_PATTERNS = {
        'checkpoint': [
            'xl', 'sd15', 'sd21', 'base', 'realistic', 'dream', 'photo',
            'portrait', 'anime', 'cartoon', 'art', 'style', 'mix'
        ],
        'lora': [
            'lora', 'lycoris', 'locon', 'loha', 'lokr', 'oft'
        ],
        'vae': [
            'vae', 'autoencoder', 'clear', 'blessed', 'anime'
        ],
        'controlnet': [
            'controlnet', 'control', 'canny', 'depth', 'openpose', 
            'scribble', 'seg', 'normal', 'lineart', 'mlsd'
        ],
        'embedding': [
            'embedding', 'textual_inversion', 'ti', 'negative'
        ]
    }
    
    # API settings
    API_PREFIX = '/api'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    
    # ComfyUI connection
    COMFYUI_HOST = 'localhost'
    COMFYUI_PORT = 8188
    COMFYUI_WEBSOCKET_URL = f'ws://{COMFYUI_HOST}:{COMFYUI_PORT}/ws'
    
    # CivitAI API
    CIVITAI_API_URL = 'https://civitai.com/api/v1'
    CIVITAI_API_KEY = os.environ.get('CIVITAI_API_KEY')
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with config"""
        # Create necessary directories
        cls.DATA_DIR.mkdir(exist_ok=True)
        cls.BACKUP_DIR.mkdir(exist_ok=True)
        cls.TEMPLATES_DIR.mkdir(exist_ok=True)
        
        # Load user settings if they exist
        settings_file = cls.DATA_DIR / 'settings.json'
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                user_settings = json.load(f)
                for key, value in user_settings.items():
                    setattr(cls, key.upper(), value)
    
    @classmethod
    def save_user_settings(cls, settings: Dict[str, Any]):
        """Save user-configurable settings"""
        settings_file = cls.DATA_DIR / 'settings.json'
        
        # Filter only user-configurable settings
        user_settings = {
            'models_directory': settings.get('models_directory', ''),
            'auto_scan': settings.get('auto_scan', True),
            'theme': settings.get('theme', 'dark'),
            'show_examples': settings.get('show_examples', True),
            'scan_recursive': settings.get('scan_recursive', True),
            'last_scan': settings.get('last_scan'),
        }
        
        with open(settings_file, 'w') as f:
            json.dump(user_settings, f, indent=2)
        
        return user_settings
    
    @classmethod
    def get_user_settings(cls) -> Dict[str, Any]:
        """Get current user settings"""
        settings_file = cls.DATA_DIR / 'settings.json'
        
        default_settings = {
            'models_directory': '',
            'auto_scan': True,
            'theme': 'dark',
            'show_examples': True,
            'scan_recursive': True,
            'last_scan': None
        }
        
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                saved_settings = json.load(f)
                default_settings.update(saved_settings)
        
        return default_settings


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Override with environment variables in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE_PATH = ':memory:'  # Use in-memory database for tests


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}