"""
Frontend routes for serving HTML and static files
"""
from flask import Blueprint, render_template, send_from_directory
from config import IMAGES_DIR
import os

bp = Blueprint('views', __name__)


@bp.route('/')
def index():
    """Serve main HTML file"""
    return render_template('index.html')


@bp.route('/images/<path:filename>')
def serve_image(filename):
    """Serve example images and videos"""
    return send_from_directory(IMAGES_DIR, filename)


@bp.route('/health')
def health_check():
    """Health check endpoint"""
    from app.services.database import load_db
    from config import DB_FILE
    
    return {
        'status': 'ok',
        'database': 'exists' if os.path.exists(DB_FILE) else 'missing',
        'models_count': len(load_db().get('models', {}))
    }