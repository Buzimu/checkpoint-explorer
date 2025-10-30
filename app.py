from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
import json
import os
import hashlib
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.config['UPLOAD_FOLDER'] = 'static/previews'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Data file path
DATA_FILE = 'data/models.json'
SETTINGS_FILE = 'data/app_settings.json'

# Model type-specific settings configuration
MODEL_TYPE_SETTINGS = {
    "checkpoint": {
        "fields": ["resolution", "sampler", "steps", "cfg_scale", "clip_skip"],
        "defaults": {
            "resolution": "512x512",
            "sampler": "DPM++ 2M Karras",
            "steps": "20",
            "cfg_scale": "7.0",
            "clip_skip": "1"
        }
    },
    "lora": {
        "fields": ["weight", "resolution", "trigger_words"],
        "defaults": {
            "weight": "0.8",
            "resolution": "512x512",
            "trigger_words": ""
        }
    },
    "embedding": {
        "fields": ["trigger_word", "weight"],
        "defaults": {
            "trigger_word": "",
            "weight": "1.0"
        }
    },
    "vae": {
        "fields": ["compatible_models"],
        "defaults": {
            "compatible_models": ""
        }
    },
    "controlnet": {
        "fields": ["preprocessor", "control_weight", "resolution"],
        "defaults": {
            "preprocessor": "none",
            "control_weight": "1.0",
            "resolution": "512x512"
        }
    },
    "clip": {
        "fields": ["compatible_models"],
        "defaults": {
            "compatible_models": ""
        }
    }
}

# Resolution options
RESOLUTION_OPTIONS = [
    "512x512", "512x768", "768x512",
    "768x768", "768x1024", "1024x768",
    "1024x1024", "1024x1536", "1536x1024"
]

# Sampler options
SAMPLER_OPTIONS = [
    "DPM++ 2M Karras", "DPM++ SDE Karras", "Euler a",
    "Euler", "LMS", "Heun", "DPM2", "DPM2 a",
    "DPM++ 2S a", "DPM++ 2M", "DPM++ SDE", "DPM fast",
    "DPM adaptive", "LMS Karras", "DPM2 Karras",
    "DPM2 a Karras", "DPM++ 2S a Karras"
]

def load_settings():
    """Load application settings"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {
        "models_directory": "",
        "auto_scan": True,
        "theme": "dark",
        "show_examples": True,
        "last_scan": None
    }

def save_settings(settings):
    """Save application settings"""
    os.makedirs('data', exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def load_models():
    """Load models from JSON file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_models(models):
    """Save models to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(models, f, indent=2, ensure_ascii=False)

def get_settings_for_model(model_type):
    """Get appropriate settings fields for a model type"""
    return MODEL_TYPE_SETTINGS.get(model_type.lower(), MODEL_TYPE_SETTINGS["checkpoint"])

def scan_models_directory(directory):
    """Scan directory for models"""
    models = []
    model_extensions = ['.safetensors', '.ckpt', '.pt', '.pth', '.bin']
    
    if not os.path.exists(directory):
        return models
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in model_extensions):
                file_path = os.path.join(root, file)
                file_stat = os.stat(file_path)
                
                # Determine model type from path
                rel_path = os.path.relpath(file_path, directory)
                model_type = "checkpoint"
                if "lora" in rel_path.lower():
                    model_type = "lora"
                elif "embedding" in rel_path.lower():
                    model_type = "embedding"
                elif "vae" in rel_path.lower():
                    model_type = "vae"
                elif "controlnet" in rel_path.lower():
                    model_type = "controlnet"
                elif "clip" in rel_path.lower():
                    model_type = "clip"
                
                # Check for readme.txt
                readme_path = file_path.rsplit('.', 1)[0] + '.txt'
                readme_content = ""
                if os.path.exists(readme_path):
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as rf:
                        readme_content = rf.read()
                
                # Get default settings for model type
                type_settings = get_settings_for_model(model_type)
                
                model = {
                    "id": hashlib.md5(file_path.encode()).hexdigest(),
                    "name": os.path.splitext(file)[0],
                    "filename": file,
                    "path": file_path,
                    "type": model_type,
                    "size": file_stat.st_size,
                    "size_formatted": format_file_size(file_stat.st_size),
                    "modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                    "preview_image": None,
                    "preview_video": None,
                    "has_video": False,
                    "rating": "pg",
                    "notes": readme_content,
                    "settings": type_settings["defaults"].copy(),
                    "links": {
                        "civitai": "",
                        "huggingface": "",
                        "github": "",
                        "custom": ""
                    },
                    "tags": []
                }
                models.append(model)
    
    return models

def format_file_size(bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.2f} PB"

@app.route('/')
def index():
    """Main page"""
    models = load_models()
    settings = load_settings()
    
    # Get unique model types for filter
    model_types = list(set(m['type'] for m in models))
    
    return render_template('index.html', 
                         models=models, 
                         settings=settings,
                         model_types=model_types,
                         resolution_options=RESOLUTION_OPTIONS,
                         sampler_options=SAMPLER_OPTIONS)

@app.route('/api/scan', methods=['POST'])
def scan_models():
    """Scan models directory"""
    settings = load_settings()
    directory = settings.get('models_directory', '')
    
    if not directory or not os.path.exists(directory):
        return jsonify({'success': False, 'error': 'Invalid models directory'})
    
    # Scan directory
    new_models = scan_models_directory(directory)
    
    # Load existing models to preserve user data
    existing_models = load_models()
    existing_by_path = {m['path']: m for m in existing_models}
    
    # Merge new and existing
    merged_models = []
    for new_model in new_models:
        if new_model['path'] in existing_by_path:
            # Preserve user data
            existing = existing_by_path[new_model['path']]
            new_model['preview_image'] = existing.get('preview_image')
            new_model['preview_video'] = existing.get('preview_video')
            new_model['has_video'] = existing.get('has_video', False)
            new_model['rating'] = existing.get('rating', 'pg')
            new_model['settings'] = existing.get('settings', new_model['settings'])
            new_model['links'] = existing.get('links', new_model['links'])
            new_model['tags'] = existing.get('tags', [])
        merged_models.append(new_model)
    
    # Save merged models
    save_models(merged_models)
    
    # Update last scan time
    settings['last_scan'] = datetime.now().isoformat()
    save_settings(settings)
    
    return jsonify({'success': True, 'count': len(merged_models)})

@app.route('/api/model/<model_id>', methods=['GET'])
def get_model(model_id):
    """Get single model details"""
    models = load_models()
    model = next((m for m in models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    
    # Add settings configuration
    model['settings_config'] = get_settings_for_model(model['type'])
    
    return jsonify({'success': True, 'model': model})

@app.route('/api/model/<model_id>', methods=['PUT'])
def update_model(model_id):
    """Update model data"""
    models = load_models()
    model = next((m for m in models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    
    data = request.json
    
    # Update fields
    if 'notes' in data:
        model['notes'] = data['notes']
    if 'settings' in data:
        model['settings'].update(data['settings'])
    if 'links' in data:
        model['links'].update(data['links'])
    if 'tags' in data:
        model['tags'] = data['tags']
    if 'rating' in data:
        model['rating'] = data['rating']
    
    save_models(models)
    
    return jsonify({'success': True, 'model': model})

@app.route('/api/update-rating', methods=['POST'])
def update_rating():
    """Update model rating"""
    data = request.json
    model_id = data.get('model_id')
    rating = data.get('rating')
    
    models = load_models()
    model = next((m for m in models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    
    model['rating'] = rating
    save_models(models)
    
    return jsonify({'success': True})

@app.route('/api/upload-preview', methods=['POST'])
def upload_preview():
    """Upload preview image or video"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    
    file = request.files['file']
    model_id = request.form.get('model_id')
    rating = request.form.get('rating', 'pg')
    
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm', '.mov'}
    ext = os.path.splitext(file.filename)[1].lower()
    
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    # Read file content for hash
    file_content = file.read()
    file_hash = hashlib.md5(file_content).hexdigest()
    file.seek(0)
    
    # Determine if video
    is_video = ext in ['.mp4', '.webm', '.mov']
    
    # Save file
    filename = f"{file_hash}{ext}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)
    
    # Update model
    models = load_models()
    model = next((m for m in models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'success': False, 'error': 'Model not found'}), 404
    
    if is_video:
        model['preview_video'] = filename
        model['has_video'] = True
    else:
        model['preview_image'] = filename
    
    model['rating'] = rating
    
    save_models(models)
    
    return jsonify({'success': True, 'filename': filename, 'is_video': is_video})

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get or update settings"""
    if request.method == 'GET':
        return jsonify(load_settings())
    else:
        data = request.json
        settings = load_settings()
        settings.update(data)
        save_settings(settings)
        return jsonify({'success': True, 'settings': settings})

@app.template_filter('get_settings_for_model')
def get_settings_for_model_filter(model_type):
    """Template filter for getting model settings"""
    return get_settings_for_model(model_type)

if __name__ == '__main__':
    app.run(debug=True, port=5000)