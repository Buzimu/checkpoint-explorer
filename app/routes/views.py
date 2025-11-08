"""
Frontend routes for serving HTML and static files
"""
from flask import Blueprint, render_template, send_from_directory
from config import IMAGES_DIR
import os
import mimetypes

bp = Blueprint('views', __name__)


@bp.route('/')
def index():
    """Serve main HTML file"""
    return render_template('index.html')


@bp.route('/images/<path:filename>')
def serve_image(filename):
    """Serve example images and videos with proper MIME types"""
    # Get the full file path
    file_path = os.path.join(IMAGES_DIR, filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        return {'error': 'File not found'}, 404
    
    # Determine MIME type
    detected_mimetype, _ = mimetypes.guess_type(filename)
    
    # Fallback MIME types for videos if guess fails
    if detected_mimetype is None:
        ext = filename.lower().split('.')[-1]
        mime_map = {
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp'
        }
        final_mimetype = mime_map.get(ext, 'application/octet-stream')
    else:
        final_mimetype = detected_mimetype
    
    return send_from_directory(IMAGES_DIR, filename, mimetype=final_mimetype)


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