"""
Settings API endpoints
"""
import os
from flask import Blueprint, jsonify, request

from backend.config import Config

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/', methods=['GET'])
def get_settings():
    """Get current application settings"""
    try:
        settings = Config.get_user_settings()
        
        # Add additional system info
        settings['version'] = Config.VERSION
        settings['app_name'] = Config.APP_NAME
        settings['supported_extensions'] = list(Config.SUPPORTED_EXTENSIONS.keys())
        
        return jsonify({
            'status': 'success',
            'settings': settings
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@settings_bp.route('/', methods=['POST'])
def update_settings():
    """Update application settings"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No settings data provided'
            }), 400
        
        # Validate models directory if provided
        if 'models_directory' in data:
            directory = data['models_directory']
            if directory and not os.path.exists(directory):
                return jsonify({
                    'status': 'error',
                    'message': f'Directory not found: {directory}'
                }), 400
        
        # Save settings
        saved_settings = Config.save_user_settings(data)
        
        return jsonify({
            'status': 'success',
            'message': 'Settings saved successfully',
            'settings': saved_settings
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@settings_bp.route('/reset', methods=['POST'])
def reset_settings():
    """Reset settings to defaults"""
    try:
        default_settings = {
            'models_directory': '',
            'auto_scan': True,
            'theme': 'dark',
            'show_examples': True,
            'scan_recursive': True,
            'last_scan': None
        }
        
        saved_settings = Config.save_user_settings(default_settings)
        
        return jsonify({
            'status': 'success',
            'message': 'Settings reset to defaults',
            'settings': saved_settings
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@settings_bp.route('/system', methods=['GET'])
def get_system_info():
    """Get system information"""
    try:
        import platform
        import psutil
        
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'platform_release': platform.release(),
            'processor': platform.processor(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total': psutil.virtual_memory().total,
            'memory_available': psutil.virtual_memory().available,
            'disk_usage': {}
        }
        
        # Get disk usage for models directory
        settings = Config.get_user_settings()
        if settings.get('models_directory'):
            try:
                usage = psutil.disk_usage(settings['models_directory'])
                system_info['disk_usage'] = {
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                }
            except:
                pass
        
        return jsonify({
            'status': 'success',
            'system': system_info
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@settings_bp.route('/export', methods=['GET'])
def export_settings():
    """Export all settings and data for backup"""
    try:
        from backend.services.notes_service import notes_service
        from backend.database import db_manager
        
        export_data = {
            'version': Config.VERSION,
            'settings': Config.get_user_settings(),
            'statistics': db_manager.get_statistics(),
            'notes': notes_service.export_all_notes()
        }
        
        return jsonify({
            'status': 'success',
            'export': export_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@settings_bp.route('/import', methods=['POST'])
def import_settings():
    """Import settings and data from backup"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No import data provided'
            }), 400
        
        # Import settings
        if 'settings' in data:
            Config.save_user_settings(data['settings'])
        
        # TODO: Import notes and other data
        
        return jsonify({
            'status': 'success',
            'message': 'Settings imported successfully'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500