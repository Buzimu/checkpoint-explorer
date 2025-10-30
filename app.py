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
            print(f"✅ Created backup: {backup_file}")
        
        # Save new data
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved database: {len(data.get('models', {}))} models")
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
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
    """Serve example images"""
    return send_from_directory(IMAGES_DIR, filename)

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