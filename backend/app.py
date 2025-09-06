"""
Flask application factory
"""
from flask import Flask, render_template
from flask_cors import CORS

from backend.config import Config
from backend.database import db_manager
from backend.api import register_blueprints
from backend.utils.errors import register_error_handlers


def create_app(config_class=Config):
    """
    Application factory pattern for creating Flask app
    
    Args:
        config_class: Configuration class to use
        
    Returns:
        Flask application instance
    """
    
    # Create Flask instance
    app = Flask(__name__, 
                template_folder=config_class.TEMPLATE_FOLDER,
                static_folder=config_class.STATIC_FOLDER,
                static_url_path='/')
    
    # Load configuration
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    # Initialize CORS for API access
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize database
    db_manager.init_app(app)
    
    # Register API blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register main route
    @app.route('/')
    def index():
        """Serve the main application page"""
        return render_template('index.html')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Simple health check endpoint"""
        return {'status': 'healthy', 'version': config_class.VERSION}
    
    return app