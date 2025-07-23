from flask import Flask, render_template, jsonify, request
import os
import json
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'comfyui-model-explorer-secret-key-change-in-production'

# Sample data for development - will be replaced with real file scanning
SAMPLE_MODELS = [
    {
        'id': 1,
        'name': 'RealisticVision v5.1',
        'type': 'Checkpoint',
        'size': '4.27 GB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-01-15',
        'path': '/models/checkpoints/realisticvision_v51.safetensors',
        'has_notes': True,
        'notes': """This model works exceptionally well for photorealistic portraits and full-body shots. 

RECOMMENDED SETTINGS:
- Resolution: 512x768 or 768x512 for best results
- Sampler: DPM++ 2M Karras (20-25 steps)
- CFG Scale: 7-8 for balanced results
- Clip Skip: 2

SUGGESTED PROMPTS:
- Add "highly detailed, sharp focus" for better quality
- Use "(photorealistic:1.2)" for enhanced realism
- Avoid over-prompting - this model responds well to simple descriptions

KNOWN ISSUES:
- May produce oversaturated colors at CFG > 10
- Works poorly with abstract/artistic styles
- Best with human subjects, struggles with complex backgrounds

TAGS: realistic, portrait, photorealism, human

CivitAI ID: 4201
Last Updated: 2024-01-15""",
        'examples': [
            {'type': 'portrait', 'prompt': 'professional portrait, detailed face, studio lighting'},
            {'type': 'full_body', 'prompt': 'full body shot, realistic proportions, natural pose'},
            {'type': 'landscape', 'prompt': 'scenic landscape, wide angle, golden hour'}
        ]
    },
    {
        'id': 2,
        'name': 'DreamShaper v8',
        'type': 'Checkpoint',
        'size': '2.13 GB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-02-10',
        'path': '/models/checkpoints/dreamshaper_v8.safetensors',
        'has_notes': False,
        'notes': '',
        'examples': []
    },
    {
        'id': 3,
        'name': 'Detail Tweaker LoRA',
        'type': 'LoRA',
        'size': '144 MB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-01-20',
        'path': '/models/loras/detail_tweaker.safetensors',
        'has_notes': True,
        'notes': 'Enhances fine details in generated images. Use weight 0.5-0.8 for best results.',
        'examples': []
    },
    {
        'id': 4,
        'name': 'Anime Face LoRA',
        'type': 'LoRA',
        'size': '87 MB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-02-05',
        'path': '/models/loras/anime_face.safetensors',
        'has_notes': False,
        'notes': '',
        'examples': []
    },
    {
        'id': 5,
        'name': 'ClearVAE v2.3',
        'type': 'VAE',
        'size': '334 MB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-01-30',
        'path': '/models/vae/clearvae_v23.safetensors',
        'has_notes': False,
        'notes': '',
        'examples': []
    },
    {
        'id': 6,
        'name': 'ControlNet Canny',
        'type': 'ControlNet',
        'size': '1.45 GB',
        'format': 'SafeTensors',
        'base_model': 'SD 1.5',
        'created': '2024-01-25',
        'path': '/models/controlnet/canny.safetensors',
        'has_notes': False,
        'notes': '',
        'examples': []
    }
]

@app.route('/')
def index():
    """Main page - shows the model explorer interface"""
    return render_template('index.html', models=SAMPLE_MODELS)

@app.route('/api/models')
def api_models():
    """API endpoint to get all models"""
    search = request.args.get('search', '').lower()
    model_type = request.args.get('type', 'all').lower()
    
    filtered_models = SAMPLE_MODELS
    
    # Filter by search term
    if search:
        filtered_models = [m for m in filtered_models if search in m['name'].lower()]
    
    # Filter by type
    if model_type != 'all':
        filtered_models = [m for m in filtered_models if m['type'].lower() == model_type]
    
    return jsonify({
        'models': filtered_models,
        'total': len(filtered_models),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/models/<int:model_id>')
def api_model_detail(model_id):
    """API endpoint to get detailed information about a specific model"""
    model = next((m for m in SAMPLE_MODELS if m['id'] == model_id), None)
    
    if not model:
        return jsonify({'error': 'Model not found'}), 404
    
    return jsonify(model)

@app.route('/api/scan')
def api_scan():
    """API endpoint to trigger a directory scan (placeholder for now)"""
    # TODO: Implement actual directory scanning
    return jsonify({
        'status': 'success',
        'message': 'Directory scan completed',
        'models_found': len(SAMPLE_MODELS),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """API endpoint for app settings"""
    if request.method == 'POST':
        # TODO: Save settings to file
        settings = request.json
        return jsonify({'status': 'success', 'message': 'Settings saved'})
    else:
        # TODO: Load settings from file
        default_settings = {
            'models_directory': '',
            'auto_scan': True,
            'theme': 'dark',
            'show_examples': True
        }
        return jsonify(default_settings)

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Create necessary directories if they don't exist
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    print("🎨 ComfyUI Model Explorer starting...")
    print("📂 Open http://localhost:5001 in your browser")
    print("🔄 Debug mode enabled - changes will auto-reload")
    
    app.run(debug=True, port=5001, host='0.0.0.0')