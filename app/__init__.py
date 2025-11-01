"""
Flask application factory for ComfyUI Model Explorer
"""
from flask import Flask
import os


def create_app(config_object='config'):
    """
    Create and configure the Flask application
    
    Args:
        config_object: Configuration object to load
        
    Returns:
        Configured Flask app instance
    """
    # Create Flask app with static/templates in app directory
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    # Load configuration
    app.config.from_object(config_object)
    
    # Ensure required directories exist
    from config import IMAGES_DIR, BACKUP_DIR
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    print(f"📂 Images directory: {IMAGES_DIR}")
    print(f"💾 Backup directory: {BACKUP_DIR}")
    
    # Register blueprints
    from app.routes import views, api, backups
    app.register_blueprint(views.bp)
    app.register_blueprint(api.bp, url_prefix='/api')
    app.register_blueprint(backups.bp, url_prefix='/api')
    
    return app