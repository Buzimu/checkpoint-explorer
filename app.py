from flask import Flask, render_template, jsonify, request
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

# Import our file scanner
from services.file_scanner import FileScanner, quick_scan

# Initialize Flask app first
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

class NotesService:
    """Enhanced service for managing model notes with templates and versioning"""
    
    TEMPLATE_DIR = "templates/notes"
    BACKUP_DIR = "backups/notes"
    
    # Note templates for different model types
    TEMPLATES = {
        'checkpoint': '''# {model_name}

## Model Information
- **Type:** Checkpoint Model
- **Base Model:** SD 1.5 / SD 2.1 / SDXL
- **Resolution:** 512x512 / 768x768 / 1024x1024
- **File Size:** {file_size}

## Recommended Settings
- **Sampler:** DPM++ 2M Karras
- **Steps:** 20-30
- **CFG Scale:** 7-9
- **Clip Skip:** 1-2

## Usage Notes
- **Best for:** [Describe what this model excels at]
- **Style:** [Artistic style or theme]
- **Trigger Words:** [Any specific trigger words]

## My Experience
- **Quality:** ⭐⭐⭐⭐⭐
- **Ease of Use:** ⭐⭐⭐⭐⭐
- **Notes:** [Your personal notes and findings]

---
*Last updated: {date}*''',

        'lora': '''# {model_name}

## Model Information
- **Type:** LoRA (Low-Rank Adaptation)
- **Base Model:** SD 1.5 / SD 2.1 / SDXL
- **Trigger Weight:** 0.5 - 1.0
- **File Size:** {file_size}

## Usage Instructions
- **Trigger Words:** [Required trigger words]
- **Recommended Weight:** 0.7-0.8
- **Best Prompts:** [Example prompts that work well]

## Settings
- **Works well with:** [Compatible checkpoints]
- **Avoid:** [Incompatible models or settings]

## Examples
- [Add your successful prompt examples here]

## My Notes
- **Quality:** ⭐⭐⭐⭐⭐
- **Versatility:** ⭐⭐⭐⭐⭐
- **Personal Notes:** [Your experience and tips]

---
*Last updated: {date}*''',

        'vae': '''# {model_name}

## Model Information
- **Type:** VAE (Variational Autoencoder)
- **Compatible with:** SD 1.5 / SD 2.1 / SDXL
- **File Size:** {file_size}

## Purpose & Usage
- **Improves:** [Color accuracy, detail, contrast, etc.]
- **Best for:** [Types of images this VAE works best with]
- **Comparison:** [How it compares to other VAEs]

## Technical Notes
- **Resolution:** [Optimal resolution settings]
- **Performance:** [Impact on generation speed]
- **Memory Usage:** [VRAM requirements]

## My Experience
- **Visual Quality:** ⭐⭐⭐⭐⭐
- **Performance Impact:** ⭐⭐⭐⭐⭐
- **Notes:** [Your observations and comparisons]

---
*Last updated: {date}*''',

        'controlnet': '''# {model_name}

## Model Information
- **Type:** ControlNet
- **Control Type:** [Canny, Depth, OpenPose, etc.]
- **Base Model:** SD 1.5 / SD 2.1 / SDXL
- **File Size:** {file_size}

## Usage Settings
- **Control Weight:** 0.8-1.2
- **Starting Step:** 0
- **Ending Step:** 1.0
- **Preprocessor:** [Required preprocessor]

## Best Use Cases
- [Describe what this ControlNet is best for]
- [Mention any specific scenarios]

## Tips & Tricks
- [Your personal tips for using this ControlNet]
- [Common issues and solutions]

## My Experience
- **Accuracy:** ⭐⭐⭐⭐⭐
- **Ease of Use:** ⭐⭐⭐⭐⭐
- **Notes:** [Your findings and recommendations]

---
*Last updated: {date}*''',

        'embedding': '''# {model_name}

## Model Information
- **Type:** Textual Inversion / Embedding
- **Base Model:** SD 1.5 / SD 2.1 / SDXL
- **Vectors:** [Number of vectors]
- **File Size:** {file_size}

## Usage Instructions
- **Trigger Word:** {model_name}
- **Placement:** [Beginning, end, or middle of prompt]
- **Weight:** Usually 1.0 (can be adjusted)

## Purpose
- **Effect:** [What this embedding does]
- **Style:** [Artistic style or effect it provides]

## Example Prompts
```
[Add your successful prompt examples here]
```

## My Notes
- **Effectiveness:** ⭐⭐⭐⭐⭐
- **Versatility:** ⭐⭐⭐⭐⭐
- **Personal Tips:** [Your experience and usage tips]

---
*Last updated: {date}*'''
    }
    
    def __init__(self):
        """Initialize the notes service"""
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories for templates and backups"""
        os.makedirs(self.TEMPLATE_DIR, exist_ok=True)
        os.makedirs(self.BACKUP_DIR, exist_ok=True)
    
    def get_notes_file_path(self, model_path: str) -> Path:
        """Get the path to the notes file for a given model"""
        model_path = Path(model_path)
        return model_path.with_suffix('.txt')
    
    def load_notes(self, model_path: str) -> Dict:
        """Load notes for a specific model"""
        notes_file = self.get_notes_file_path(model_path)
        
        try:
            if notes_file.exists():
                with open(notes_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                return {
                    'status': 'success',
                    'content': content,
                    'has_notes': bool(content.strip()),
                    'file_path': str(notes_file),
                    'last_modified': datetime.fromtimestamp(notes_file.stat().st_mtime).isoformat(),
                    'word_count': len(content.split()) if content.strip() else 0,
                    'char_count': len(content)
                }
            else:
                return {
                    'status': 'success',
                    'content': '',
                    'has_notes': False,
                    'file_path': str(notes_file),
                    'last_modified': None,
                    'word_count': 0,
                    'char_count': 0
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to load notes: {str(e)}',
                'content': '',
                'has_notes': False
            }
    
    def save_notes(self, model_path: str, content: str, create_backup: bool = True) -> Dict:
        """Save notes for a specific model with optional backup"""
        notes_file = self.get_notes_file_path(model_path)
        
        try:
            # Create backup if file exists and backup is requested
            if create_backup and notes_file.exists():
                self._create_backup(notes_file)
            
            # Write the new content
            with open(notes_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                'status': 'success',
                'message': 'Notes saved successfully',
                'file_path': str(notes_file),
                'backup_created': create_backup and notes_file.exists(),
                'word_count': len(content.split()) if content.strip() else 0,
                'char_count': len(content),
                'saved_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to save notes: {str(e)}'
            }
    
    def _create_backup(self, notes_file: Path):
        """Create a timestamped backup of the notes file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{notes_file.stem}_backup_{timestamp}.txt"
            backup_path = Path(self.BACKUP_DIR) / backup_name
            
            shutil.copy2(notes_file, backup_path)
            print(f"📄 Created backup: {backup_path}")
            
        except Exception as e:
            print(f"⚠️ Failed to create backup: {e}")
    
    def get_template(self, model_type: str, model_name: str, file_size: str) -> str:
        """Get a formatted template for a specific model type"""
        template = self.TEMPLATES.get(model_type.lower(), self.TEMPLATES['checkpoint'])
        
        # Replace placeholders
        return template.format(
            model_name=model_name,
            file_size=file_size,
            date=datetime.now().strftime('%Y-%m-%d')
        )
    
    def get_available_templates(self) -> List[Dict]:
        """Get list of available note templates"""
        return [
            {
                'id': 'checkpoint',
                'name': 'Checkpoint Model',
                'description': 'Standard template for checkpoint models'
            },
            {
                'id': 'lora',
                'name': 'LoRA Model', 
                'description': 'Template for LoRA fine-tuning models'
            },
            {
                'id': 'vae',
                'name': 'VAE Model',
                'description': 'Template for VAE models'
            },
            {
                'id': 'controlnet',
                'name': 'ControlNet',
                'description': 'Template for ControlNet models'
            },
            {
                'id': 'embedding',
                'name': 'Embedding',
                'description': 'Template for textual inversions'
            }
        ]
    
    def get_backups(self, model_path: str) -> List[Dict]:
        """Get available backups for a specific model"""
        model_name = Path(model_path).stem
        backups = []
        
        try:
            backup_dir = Path(self.BACKUP_DIR)
            pattern = f"{model_name}_backup_*.txt"
            
            for backup_file in backup_dir.glob(pattern):
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'size': stat.st_size
                })
            
            # Sort by creation time, newest first
            backups.sort(key=lambda x: x['created'], reverse=True)
            
        except Exception as e:
            print(f"⚠️ Failed to get backups: {e}")
        
        return backups
    
    def restore_backup(self, model_path: str, backup_filename: str) -> Dict:
        """Restore a specific backup for a model"""
        try:
            backup_path = Path(self.BACKUP_DIR) / backup_filename
            notes_file = self.get_notes_file_path(model_path)
            
            if not backup_path.exists():
                return {
                    'status': 'error',
                    'message': 'Backup file not found'
                }
            
            # Create backup of current file before restoring
            if notes_file.exists():
                self._create_backup(notes_file)
            
            # Copy backup to notes file
            shutil.copy2(backup_path, notes_file)
            
            return {
                'status': 'success',
                'message': 'Backup restored successfully',
                'restored_from': backup_filename
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Failed to restore backup: {str(e)}'
            }

# Initialize notes service
notes_service = NotesService()

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

# Enhanced Notes API endpoints
@app.route('/api/notes/<int:model_id>', methods=['GET', 'POST', 'PUT'])
def api_model_notes_enhanced(model_id):
    """Enhanced API endpoint for model notes with templates and versioning"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    if request.method == 'GET':
        # Load existing notes
        result = notes_service.load_notes(model['path'])
        
        # Add additional metadata
        result.update({
            'model_id': model_id,
            'model_name': model['name'],
            'model_type': model['type'],
            'available_templates': notes_service.get_available_templates(),
            'backups': notes_service.get_backups(model['path'])
        })
        
        return jsonify(result)
    
    elif request.method in ['POST', 'PUT']:
        # Save notes
        data = request.get_json()
        content = data.get('content', '')
        create_backup = data.get('create_backup', True)
        
        result = notes_service.save_notes(model['path'], content, create_backup)
        
        if result['status'] == 'success':
            # Update model in memory
            model['notes'] = content
            model['has_notes'] = bool(content.strip())
        
        return jsonify(result)

@app.route('/api/notes/<int:model_id>/template/<template_type>')
def api_get_note_template(model_id, template_type):
    """Get a formatted template for a specific model"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    template_content = notes_service.get_template(
        template_type, 
        model['name'], 
        model['size']
    )
    
    return jsonify({
        'status': 'success',
        'template_type': template_type,
        'content': template_content,
        'model_name': model['name']
    })

@app.route('/api/notes/<int:model_id>/backups')
def api_get_note_backups(model_id):
    """Get available backups for a model's notes"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    backups = notes_service.get_backups(model['path'])
    
    return jsonify({
        'status': 'success',
        'backups': backups,
        'model_name': model['name']
    })

@app.route('/api/notes/<int:model_id>/restore', methods=['POST'])
def api_restore_note_backup(model_id):
    """Restore a backup for a model's notes"""
    model = next((m for m in current_models if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    data = request.get_json()
    backup_filename = data.get('backup_filename')
    
    if not backup_filename:
        return jsonify({'error': 'Backup filename required'}), 400
    
    result = notes_service.restore_backup(model['path'], backup_filename)
    
    if result['status'] == 'success':
        # Reload notes into memory
        notes_data = notes_service.load_notes(model['path'])
        model['notes'] = notes_data['content']
        model['has_notes'] = notes_data['has_notes']
    
    return jsonify(result)

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

@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests"""
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