"""
API Blueprint registration and initialization
"""
from flask import Flask

from backend.api.models_api import models_bp
from backend.api.notes_api import notes_bp
from backend.api.settings_api import settings_bp
from backend.api.scan_api import scan_bp


def register_blueprints(app: Flask):
    """
    Register all API blueprints with the Flask app
    
    Args:
        app: Flask application instance
    """
    # Register blueprints with API prefix
    api_prefix = app.config.get('API_PREFIX', '/api')
    
    app.register_blueprint(models_bp, url_prefix=f'{api_prefix}/models')
    app.register_blueprint(notes_bp, url_prefix=f'{api_prefix}/notes')
    app.register_blueprint(settings_bp, url_prefix=f'{api_prefix}/settings')
    app.register_blueprint(scan_bp, url_prefix=f'{api_prefix}/scan')
    
    # Log registered routes for debugging
    if app.config.get('DEBUG'):
        print("\n📍 Registered API routes:")
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                methods = ', '.join(rule.methods - {'HEAD', 'OPTIONS'})
                print(f"  {rule.rule} [{methods}] -> {rule.endpoint}")
        print()


__all__ = ['register_blueprints']