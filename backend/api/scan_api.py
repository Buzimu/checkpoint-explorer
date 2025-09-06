"""
Directory scanning API endpoints
"""
import os
from flask import Blueprint, jsonify, request
from threading import Thread

from backend.services.file_scanner import file_scanner
from backend.database import db_manager
from backend.config import Config

scan_bp = Blueprint('scan', __name__)

# Global scan status (in production, use Redis or similar)
scan_status = {
    'active': False,
    'progress': 0,
    'total': 0,
    'current_file': '',
    'message': '',
    'errors': []
}


def progress_callback(current: int, total: int, filename: str):
    """Update scan progress"""
    global scan_status
    scan_status['progress'] = current
    scan_status['total'] = total
    scan_status['current_file'] = filename
    scan_status['message'] = f'Processing {filename}... ({current}/{total})'


def run_scan(directory: str, recursive: bool = True):
    """Run scan in background thread"""
    global scan_status
    
    try:
        scan_status['active'] = True
        scan_status['message'] = 'Starting scan...'
        
        # Perform scan
        models, stats = file_scanner.scan_directory(
            directory,
            recursive=recursive,
            progress_callback=progress_callback
        )
        
        # Update user settings
        settings = Config.get_user_settings()
        settings['models_directory'] = directory
        settings['last_scan'] = stats.get('completed_at')
        Config.save_user_settings(settings)
        
        scan_status['message'] = f'Scan complete! Found {len(models)} models'
        scan_status['stats'] = stats
        
    except Exception as e:
        scan_status['message'] = f'Scan failed: {str(e)}'
        scan_status['errors'].append(str(e))
        
    finally:
        scan_status['active'] = False


@scan_bp.route('/', methods=['POST'])
def start_scan():
    """Start a directory scan"""
    try:
        data = request.get_json() or {}
        directory = data.get('directory', '').strip()
        recursive = data.get('recursive', True)
        
        # Use saved directory if none provided
        if not directory:
            settings = Config.get_user_settings()
            directory = settings.get('models_directory')
        
        if not directory:
            return jsonify({
                'status': 'error',
                'message': 'No directory specified'
            }), 400
        
        if not os.path.exists(directory):
            return jsonify({
                'status': 'error',
                'message': f'Directory not found: {directory}'
            }), 404
        
        if not os.path.isdir(directory):
            return jsonify({
                'status': 'error',
                'message': 'Path is not a directory'
            }), 400
        
        # Check if scan is already running
        if scan_status['active']:
            return jsonify({
                'status': 'error',
                'message': 'Scan already in progress'
            }), 409
        
        # Reset scan status
        scan_status.update({
            'active': True,
            'progress': 0,
            'total': 0,
            'current_file': '',
            'message': 'Initializing scan...',
            'errors': []
        })
        
        # Start scan in background thread
        thread = Thread(target=run_scan, args=(directory, recursive))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Scan started',
            'directory': directory
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@scan_bp.route('/status', methods=['GET'])
def get_scan_status():
    """Get current scan status"""
    return jsonify({
        'status': 'success',
        'scan': scan_status
    })


@scan_bp.route('/validate', methods=['POST'])
def validate_directory():
    """Validate a directory before scanning"""
    try:
        data = request.get_json() or {}
        directory = data.get('directory', '').strip()
        
        if not directory:
            return jsonify({
                'valid': False,
                'message': 'Directory path is required'
            }), 400
        
        if not os.path.exists(directory):
            return jsonify({
                'valid': False,
                'message': 'Directory does not exist'
            }), 404
        
        if not os.path.isdir(directory):
            return jsonify({
                'valid': False,
                'message': 'Path is not a directory'
            }), 400
        
        # Quick check for model files
        has_models = False
        count = 0
        
        for root, dirs, files in os.walk(directory):
            for file in files[:50]:  # Check first 50 files
                if any(file.lower().endswith(ext) for ext in Config.SUPPORTED_EXTENSIONS):
                    has_models = True
                    count += 1
                    if count >= 5:
                        break
            if count >= 5:
                break
        
        if not has_models:
            return jsonify({
                'valid': True,
                'message': 'Directory exists but no model files found',
                'warning': True
            })
        
        return jsonify({
            'valid': True,
            'message': f'Directory looks good! Found {count}+ model files'
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'message': str(e)
        }), 500


@scan_bp.route('/history', methods=['GET'])
def get_scan_history():
    """Get scan history"""
    try:
        limit = request.args.get('limit', 10, type=int)
        history = db_manager.get_scan_history(limit)
        
        return jsonify({
            'status': 'success',
            'history': history
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@scan_bp.route('/refresh', methods=['POST'])
def refresh_models():
    """Quick refresh of current directory"""
    try:
        settings = Config.get_user_settings()
        directory = settings.get('models_directory')
        
        if not directory:
            return jsonify({
                'status': 'error',
                'message': 'No models directory configured'
            }), 400
        
        if not os.path.exists(directory):
            return jsonify({
                'status': 'error',
                'message': f'Directory not found: {directory}'
            }), 404
        
        # Check if scan is already running
        if scan_status['active']:
            return jsonify({
                'status': 'error',
                'message': 'Scan already in progress'
            }), 409
        
        # Start refresh scan
        thread = Thread(target=run_scan, args=(directory, True))
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Refresh started'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500