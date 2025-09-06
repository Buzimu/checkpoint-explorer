"""
Notes API endpoints
"""
from flask import Blueprint, jsonify, request

from backend.services.notes_service import notes_service
from backend.database import db_manager
from backend.utils.validators import validate_model_id, validate_notes_content

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/<model_id>', methods=['GET'])
def get_notes(model_id: str):
    """Get notes for a specific model"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        result = notes_service.get_notes(model_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/<model_id>', methods=['POST'])
def save_notes(model_id: str):
    """Save notes for a specific model"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        content = data.get('content', '')
        create_backup = data.get('create_backup', True)
        
        # Validate notes content
        validation = validate_notes_content(content)
        if not validation['valid']:
            return jsonify({
                'status': 'error',
                'message': validation['message']
            }), 400
        
        result = notes_service.save_notes(model_id, content, create_backup)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/<model_id>/template/<template_type>', methods=['GET'])
def get_notes_template(model_id: str, template_type: str):
    """Get a formatted template for a specific model"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        # Get model data for template variables
        model = db_manager.get_model(model_id)
        
        if not model:
            return jsonify({
                'status': 'error',
                'message': 'Model not found'
            }), 404
        
        template_content = notes_service.get_template(template_type, model)
        
        return jsonify({
            'status': 'success',
            'template_type': template_type,
            'content': template_content,
            'model_name': model['name']
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/templates', methods=['GET'])
def get_available_templates():
    """Get list of available note templates"""
    try:
        templates = notes_service.get_available_templates()
        
        return jsonify({
            'status': 'success',
            'templates': templates
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/<model_id>/backups', methods=['GET'])
def get_notes_backups(model_id: str):
    """Get available backups for a model's notes"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        backups = notes_service.get_backups(model_id)
        
        return jsonify({
            'status': 'success',
            'backups': backups,
            'model_id': model_id
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/<model_id>/restore', methods=['POST'])
def restore_notes_backup(model_id: str):
    """Restore a backup for a model's notes"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No restore data provided'
            }), 400
        
        backup_id = data.get('backup_id')
        backup_filename = data.get('backup_filename')
        
        if not backup_id and not backup_filename:
            return jsonify({
                'status': 'error',
                'message': 'Either backup_id or backup_filename is required'
            }), 400
        
        result = notes_service.restore_backup(model_id, backup_id, backup_filename)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/export', methods=['GET'])
def export_all_notes():
    """Export all notes for backup or migration"""
    try:
        result = notes_service.export_all_notes()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@notes_bp.route('/<model_id>/statistics', methods=['GET'])
def get_notes_statistics(model_id: str):
    """Get statistics about a model's notes"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        notes_data = notes_service.get_notes(model_id)
        
        if notes_data['status'] != 'success':
            return jsonify(notes_data)
        
        # Get additional statistics
        history = db_manager.get_notes_history(model_id)
        
        statistics = {
            'char_count': notes_data.get('char_count', 0),
            'word_count': notes_data.get('word_count', 0),
            'line_count': len(notes_data.get('content', '').splitlines()),
            'history_count': len(history),
            'last_modified': notes_data.get('last_modified'),
            'has_backups': len(notes_data.get('backups', [])) > 0
        }
        
        return jsonify({
            'status': 'success',
            'statistics': statistics
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500