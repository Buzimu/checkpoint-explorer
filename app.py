from flask import Flask, render_template, jsonify, request
import os
import json
from datetime import datetime
from pathlib import Path

# Import our file scanner
from services.file_scanner import FileScanner, quick_scan

app = Flask(__name__)
app.config['SECRET_KEY'] = 'comfyui-model-explorer-secret-key-change-in-production'

# Global variables for model data and settings
current_models = []
app_settings = {
    'models_directory': '',
    'auto_scan': True,
    'theme': 'dark',
    'show_examples': True,
    'last_scan': None
}

# Settings file path
SETTINGS_FILE = 'app_settings.json'

def load_settings():
    """Load settings from JSON file"""
    global app_settings
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                saved_settings = json.load(f)
                app_settings.update(saved_settings)
                print(f"📄 Loaded settings: {app_settings['models_directory']}")
    except Exception as e:
        print(f"⚠️ Failed to load settings: {e}")

def save_settings():
    """Save settings to JSON file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(app_settings, f, indent=2)
    except Exception as e:
        print(f"⚠️ Failed to save settings: {e}")

def scan_models_directory():
    """Scan the configured models directory"""
    global current_models
    
    if not app_settings['models_directory'] or not os.path.exists(app_settings['models_directory']):
        print("⚠️ No valid models directory configured")
        return []
    
    try:
        print(f"🔍 Scanning models directory: {app_settings['models_directory']}")
        
        # Import here to avoid circular imports
        from services.file_scanner import FileScanner, quick_scan
        
        models, stats = quick_scan(app_settings['models_directory'])
        current_models = models
        app_settings['last_scan'] = datetime.now().isoformat()
        
        print(f"✅ Found {len(models)} models:")
        for model_type, count in stats['by_type'].items():
            print(f"   - {count} {model_type}(s)")
            
        if len(models) == 0:
            print(f"⚠️ No models found in {app_settings['models_directory']}")
            print("💡 Make sure the directory contains .safetensors, .ckpt, .pt, .pth, or .bin files")
        
        save_settings()
        return models
        
    except Exception as e:
        print(f"❌ Failed to scan models directory: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.route('/')
def index():
    """Main page - shows the model explorer interface"""
    # Ensure we have models loaded
    if not current_models and app_settings['models_directory']:
        scan_models_directory()
    
    return render_template('index.html', models=current_models)

@app.route('/api/models')
def api_models():
    """API endpoint to get all models"""
    search = request.args.get('search', '').lower()
    model_type = request.args.get('type', 'all').lower()
    
    # Use file scanner's filter method
    scanner = FileScanner()
    filtered_models = scanner.filter_models(current_models, search, model_type)
    
    return jsonify({
        'models': filtered_models,
        'total': len(filtered_models),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/models/<int:model_id>')
def api_model_detail(model_id):
    """API endpoint to get detailed information about a specific model"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    return jsonify(model)

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """API endpoint to trigger a directory scan"""
    try:
        # Get directory from request if provided
        data = request.get_json() or {}
        new_directory = data.get('directory')
        print(f"🔍 Scan request for directory: {new_directory}")
        
        if new_directory:
            if not os.path.exists(new_directory):
                return jsonify({
                    'status': 'error',
                    'message': f'Directory not found: {new_directory}'
                }), 400
            
            app_settings['models_directory'] = new_directory
            save_settings()
            print(f"📁 Updated models directory to: {new_directory}")
        
        # Use current directory if none provided
        scan_directory = new_directory or app_settings['models_directory']
        
        if not scan_directory:
            return jsonify({
                'status': 'error',
                'message': 'No models directory configured'
            }), 400
        
        # Perform scan
        print(f"🚀 Starting scan of: {scan_directory}")
        models = scan_models_directory()
        
        return jsonify({
            'status': 'success',
            'message': 'Directory scan completed',
            'models_found': len(models),
            'directory': app_settings['models_directory'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Scan error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Scan failed: {str(e)}'
        }), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """API endpoint for app settings"""
    if request.method == 'POST':
        try:
            new_settings = request.get_json()
            print(f"📝 Received settings update: {new_settings}")
            
            if not new_settings:
                return jsonify({
                    'status': 'error',
                    'message': 'No settings data received'
                }), 400
            
            # Validate models directory if provided
            if 'models_directory' in new_settings:
                directory = new_settings['models_directory']
                if directory and not os.path.exists(directory):
                    return jsonify({
                        'status': 'error',
                        'message': f'Directory not found: {directory}'
                    }), 400
                    
                # Check if directory contains any model files
                if directory:
                    scanner = FileScanner()
                    test_models = scanner.scan_directory(directory)
                    print(f"🔍 Test scan found {len(test_models)} models in {directory}")
            
            # Update settings
            app_settings.update(new_settings)
            save_settings()
            print(f"✅ Settings updated: {app_settings}")
            
            return jsonify({
                'status': 'success',
                'message': 'Settings saved successfully',
                'settings': app_settings
            })
            
        except Exception as e:
            print(f"❌ Settings error: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to save settings: {str(e)}'
            }), 500
    else:
        print(f"📄 Returning current settings: {app_settings}")
        return jsonify(app_settings)

@app.route('/api/stats')
def api_stats():
    """API endpoint to get model collection statistics"""
    if not current_models:
        return jsonify({
            'total_models': 0,
            'by_type': {},
            'with_notes': 0,
            'total_size_gb': 0,
            'last_scan': app_settings.get('last_scan')
        })
    
    # Calculate stats
    stats = {
        'total_models': len(current_models),
        'by_type': {},
        'with_notes': sum(1 for m in current_models if m['has_notes']),
        'total_size_gb': round(sum(m['size_bytes'] for m in current_models) / (1024**3), 2),
        'last_scan': app_settings.get('last_scan')
    }
    
    # Count by type
    for model in current_models:
        model_type = model['type']
        stats['by_type'][model_type] = stats['by_type'].get(model_type, 0) + 1
    
    return jsonify(stats)

@app.route('/api/notes/<int:model_id>', methods=['GET', 'POST'])
def api_model_notes(model_id):
    """API endpoint to get or update model notes"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            new_notes = data.get('notes', '')
            
            # Write notes to companion .txt file
            model_path = Path(model['path'])
            notes_file = model_path.with_suffix('.txt')
            
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(new_notes)
            
            # Update model in memory
            model['notes'] = new_notes
            model['has_notes'] = bool(new_notes.strip())
            
            return jsonify({
                'status': 'success',
                'message': 'Notes updated successfully'
            })
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Failed to update notes: {str(e)}'
            }), 500
    else:
        return jsonify({
            'notes': model.get('notes', ''),
            'has_notes': model.get('has_notes', False)
        })

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests"""
    # Return a simple response to avoid 500 errors
    from flask import make_response
    response = make_response()
    response.status_code = 204  # No Content
    return response

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({'error': 'Internal server error'}), 500


# Add these enhancements to your existing app.py

@app.route('/api/scan_progress')
def api_scan_progress():
    """API endpoint to get scan progress (for future WebSocket implementation)"""
    return jsonify({
        'status': 'idle',  # or 'scanning', 'complete', 'error'
        'progress': 0,
        'current_file': '',
        'total_files': 0,
        'processed_files': 0
    })

@app.route('/api/validate_directory', methods=['POST'])
def api_validate_directory():
    """Validate a directory before scanning"""
    try:
        data = request.get_json() or {}
        directory = data.get('directory', '').strip()
        
        if not directory:
            return jsonify({'valid': False, 'message': 'Directory path is required'})
        
        if not os.path.exists(directory):
            return jsonify({'valid': False, 'message': 'Directory does not exist'})
        
        if not os.path.isdir(directory):
            return jsonify({'valid': False, 'message': 'Path is not a directory'})
        
        # Quick check for model files
        scanner = FileScanner()
        quick_count = 0
        for root, dirs, files in os.walk(directory):
            for file in files[:50]:  # Only check first 50 files for speed
                if any(file.lower().endswith(ext) for ext in scanner.SUPPORTED_EXTENSIONS):
                    quick_count += 1
                    if quick_count >= 5:  # Found enough to confirm it's a models directory
                        break
            if quick_count >= 5:
                break
        
        if quick_count == 0:
            return jsonify({
                'valid': True, 
                'message': 'Directory exists but no model files found. This might not be a models directory.',
                'warning': True
            })
        
        return jsonify({
            'valid': True, 
            'message': f'Directory looks good! Found {quick_count}+ model files.',
            'estimated_models': quick_count
        })
        
    except Exception as e:
        return jsonify({'valid': False, 'message': f'Error validating directory: {str(e)}'})

@app.route('/api/models/refresh')
def api_refresh_models():
    """Force refresh models from current directory"""
    try:
        if not app_settings['models_directory']:
            return jsonify({'status': 'error', 'message': 'No models directory configured'}), 400
        
        models = scan_models_directory()
        return jsonify({
            'status': 'success',
            'models_found': len(models),
            'message': 'Models refreshed successfully'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Enhanced model type filter endpoint
@app.route('/api/model_types')
def api_model_types():
    """Get available model types and their counts"""
    type_counts = {}
    for model in current_models:
        model_type = model.get('type', 'Unknown')
        type_counts[model_type] = type_counts.get(model_type, 0) + 1
    
    return jsonify({
        'types': type_counts,
        'total': len(current_models)
    })




def initialize_app():
    """Initialize app with settings and initial scan"""
    # Create necessary directories
    os.makedirs('services', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Load settings
    load_settings()
    
    # Perform initial scan if directory is configured
    if app_settings['models_directory'] and app_settings['auto_scan']:
        scan_models_directory()
    
    print("🎨 ComfyUI Model Explorer initialized!")
    print(f"📂 Models directory: {app_settings['models_directory'] or 'Not configured'}")
    print(f"📊 Models loaded: {len(current_models)}")

if __name__ == '__main__':
    initialize_app()
    
    print("\n🎨 ComfyUI Model Explorer starting...")
    print("📂 Open http://localhost:5001 in your browser")
    print("🔄 Debug mode enabled - changes will auto-reload")
    print("\n💡 First time setup:")
    print("   1. Open the app in your browser")
    print("   2. Go to settings and point to your ComfyUI models directory")
    print("   3. Click 'Scan Models' to load your collection")
    
    app.run(debug=True, port=5001, host='0.0.0.0')