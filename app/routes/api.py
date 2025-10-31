"""
API routes for model data operations
"""
from flask import Blueprint, jsonify, request
from app.services.database import load_db, save_db
from app.services.media import save_uploaded_file
import subprocess

bp = Blueprint('api', __name__)


@bp.route('/models', methods=['GET'])
def get_models():
    """Load entire database"""
    db = load_db()
    return jsonify(db)


@bp.route('/models', methods=['PUT'])
def update_all_models():
    """Update entire database"""
    try:
        data = request.json
        if save_db(data):
            return jsonify({'success': True, 'message': 'Database saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save database'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>', methods=['PUT'])
def update_model(model_path):
    """Update a specific model"""
    try:
        db = load_db()
        if model_path in db['models']:
            db['models'][model_path] = request.json
            if save_db(db):
                return jsonify({'success': True, 'model': db['models'][model_path]})
            else:
                return jsonify({'success': False, 'error': 'Failed to save'}), 500
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/favorite', methods=['POST'])
def toggle_favorite(model_path):
    """Toggle favorite status"""
    try:
        db = load_db()
        if model_path in db['models']:
            current = db['models'][model_path].get('favorite', False)
            db['models'][model_path]['favorite'] = not current
            if save_db(db):
                return jsonify({
                    'success': True,
                    'favorite': db['models'][model_path]['favorite']
                })
            else:
                return jsonify({'success': False, 'error': 'Failed to save'}), 500
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/upload-media', methods=['POST'])
def upload_media():
    """Upload image or video for a model"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        model_path = request.form.get('modelPath')
        
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read and save file
        file_content = file.read()
        filename = save_uploaded_file(file_content, file.filename)
        
        if not filename:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        print(f"✅ Uploaded media: {filename} for model: {model_path}")
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/add-media', methods=['POST'])
def add_media_to_model(model_path):
    """Add uploaded media to model's exampleImages"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        rating = data.get('rating', 'pg')
        caption = data.get('caption', '')
        
        # Add to exampleImages
        if 'exampleImages' not in db['models'][model_path]:
            db['models'][model_path]['exampleImages'] = []
        
        db['models'][model_path]['exampleImages'].append({
            'filename': filename,
            'rating': rating,
            'caption': caption
        })
        
        if save_db(db):
            print(f"✅ Added media {filename} to model {model_path}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Add media failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/update-media-rating', methods=['POST'])
def update_media_rating(model_path):
    """Update rating for a specific media item"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        new_rating = data.get('rating')
        
        if not filename or not new_rating:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
        
        # Find and update the media item
        media_list = db['models'][model_path].get('exampleImages', [])
        updated = False
        
        for media in media_list:
            if media['filename'] == filename:
                media['rating'] = new_rating
                updated = True
                break
        
        if not updated:
            return jsonify({'success': False, 'error': 'Media not found'}), 404
        
        if save_db(db):
            print(f"✅ Updated rating for {filename} to {new_rating}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Update rating failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/models/<path:model_path>/delete-media', methods=['POST'])
def delete_media(model_path):
    """Delete a media item from model's exampleImages"""
    try:
        db = load_db()
        if model_path not in db['models']:
            return jsonify({'success': False, 'error': 'Model not found'}), 404
        
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'error': 'Missing filename'}), 400
        
        # Remove from exampleImages
        media_list = db['models'][model_path].get('exampleImages', [])
        original_length = len(media_list)
        
        db['models'][model_path]['exampleImages'] = [
            media for media in media_list 
            if media['filename'] != filename
        ]
        
        if len(db['models'][model_path]['exampleImages']) == original_length:
            return jsonify({'success': False, 'error': 'Media not found'}), 404
        
        if save_db(db):
            print(f"✅ Deleted media {filename} from model {model_path}")
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to save'}), 500
            
    except Exception as e:
        print(f"❌ Delete media failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/scan', methods=['POST'])
def trigger_scan():
    """Trigger PowerShell script to scan for new models"""
    try:
        from config import MODELS_DIR
        result = subprocess.run(
            ['pwsh', '-File', 'generate-modeldb.ps1'],
            cwd=MODELS_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return jsonify({
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr if result.returncode != 0 else None
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Scan timed out after 5 minutes'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'PowerShell or script not found'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500