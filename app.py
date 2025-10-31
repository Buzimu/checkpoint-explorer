"""
ComfyUI Model Explorer - Flask Server
Simple server for automatic JSON management
"""
from flask import Flask, jsonify, request, send_from_directory
import json
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__, static_folder='.')

# Configuration
MODELS_DIR = os.getenv('MODELS_DIR', os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(MODELS_DIR, 'modeldb.json')
IMAGES_DIR = os.path.join(MODELS_DIR, 'images')

# Ensure directories exist
os.makedirs(IMAGES_DIR, exist_ok=True)

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
            print(f"âœ… Created backup: {backup_file}")
        
        # Save new data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"âœ… Saved database: {len(data.get('models', {}))} models")
        return True
    except Exception as e:
        print(f"âŒ Error saving database: {e}")
        return False

# Serve frontend files
@app.route('/')
def index():
    """Serve main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Serve static files (CSS, JS, etc.)"""
    return send_from_directory('.', path)

# API Endpoints
@app.route('/api/models', methods=['GET'])
def get_models():
    """Load entire database"""
    db = load_db()
    return jsonify(db)

@app.route('/api/models', methods=['PUT'])
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

@app.route('/api/models/<path:model_path>', methods=['PUT'])
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

@app.route('/api/models/<path:model_path>/favorite', methods=['POST'])
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

@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve example images and videos"""
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/api/upload-media', methods=['POST'])
def upload_media():
    """Upload image or video for a model"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        model_path = request.form.get('modelPath')
        
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Validate file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in allowed_extensions:
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400
        
        # Generate hash-based filename
        import hashlib
        file_content = file.read()
        file_hash = hashlib.sha256(file_content).hexdigest()[:16]
        filename = f"{file_hash}{ext}"
        
        # Save file
        file_path = os.path.join(IMAGES_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        print(f"✅ Uploaded media: {filename} for model: {model_path}")
        return jsonify({'success': True, 'filename': filename})
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/models/<path:model_path>/add-media', methods=['POST'])
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


@app.route('/api/models/<path:model_path>/update-media-rating', methods=['POST'])
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


@app.route('/api/models/<path:model_path>/delete-media', methods=['POST'])
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


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    """Trigger PowerShell script to scan for new models"""
    try:
        import subprocess
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

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'database': 'exists' if os.path.exists(DB_FILE) else 'missing',
        'models_count': len(load_db().get('models', {}))
    })

if __name__ == '__main__':
    print("\n🎨 ComfyUI Model Explorer - Flask Server")
    print("=" * 50)
    print(f"📂 Models Directory: {MODELS_DIR}")
    print(f"💾 Database File: {DB_FILE}")
    print(f"🖼️  Images Directory: {IMAGES_DIR}")
    print("=" * 50)
    
    # Check if database exists
    if os.path.exists(DB_FILE):
        db = load_db()
        print(f"✅ Database loaded: {len(db.get('models', {}))} models")
    else:
        print("⚠️  No database file found - will create on first save")
    
    print("\n🚀 Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )