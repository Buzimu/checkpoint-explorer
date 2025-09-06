"""
Models API endpoints
"""
from flask import Blueprint, jsonify, request
from typing import Dict, Any

from backend.database import db_manager
from backend.services.file_scanner import file_scanner
from backend.utils.validators import validate_model_id

models_bp = Blueprint('models', __name__)


@models_bp.route('/', methods=['GET'])
def get_models():
    """
    Get all models with optional filtering
    
    Query params:
        - search: Search term for name/notes
        - type: Filter by model type
        - has_notes: Filter models with notes
        - sort: Sort field (name, size, date)
        - order: Sort order (asc, desc)
    """
    try:
        # Get query parameters
        filters = {
            'search': request.args.get('search', ''),
            'type': request.args.get('type', 'all'),
            'has_notes': request.args.get('has_notes', type=bool)
        }
        
        # Get models from database
        models = db_manager.get_all_models(filters)
        
        # Apply sorting if requested
        sort_field = request.args.get('sort', 'name')
        sort_order = request.args.get('order', 'asc')
        
        if sort_field in ['name', 'size_bytes', 'created_at', 'modified_at']:
            models.sort(
                key=lambda x: x.get(sort_field, ''),
                reverse=(sort_order == 'desc')
            )
        
        return jsonify({
            'status': 'success',
            'models': models,
            'total': len(models),
            'filters': filters
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/<model_id>', methods=['GET'])
def get_model(model_id: str):
    """Get detailed information about a specific model"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        model = db_manager.get_model(model_id)
        
        if not model:
            return jsonify({
                'status': 'error',
                'message': 'Model not found'
            }), 404
        
        # Add computed fields
        model['has_civitai'] = bool(model.get('civitai_model_id'))
        model['tags_list'] = db_manager.get_model_tags(model_id)
        
        return jsonify({
            'status': 'success',
            'model': model
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/<model_id>', methods=['DELETE'])
def delete_model(model_id: str):
    """Delete a model from the database (not the file)"""
    try:
        if not validate_model_id(model_id):
            return jsonify({
                'status': 'error',
                'message': 'Invalid model ID format'
            }), 400
        
        success = db_manager.delete_model(model_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Model removed from database'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Model not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/<model_id>/tags', methods=['GET'])
def get_model_tags(model_id: str):
    """Get tags for a specific model"""
    try:
        tags = db_manager.get_model_tags(model_id)
        
        return jsonify({
            'status': 'success',
            'tags': tags
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/<model_id>/tags', methods=['POST'])
def add_model_tag(model_id: str):
    """Add a tag to a model"""
    try:
        data = request.get_json()
        tag_name = data.get('tag')
        
        if not tag_name:
            return jsonify({
                'status': 'error',
                'message': 'Tag name required'
            }), 400
        
        success = db_manager.add_model_tag(model_id, tag_name)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Tag added successfully'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to add tag'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/<model_id>/hash', methods=['POST'])
def generate_model_hash(model_id: str):
    """Generate hash for a model file (expensive operation)"""
    try:
        model = db_manager.get_model(model_id)
        
        if not model:
            return jsonify({
                'status': 'error',
                'message': 'Model not found'
            }), 404
        
        # Generate hash
        hash_value = file_scanner.generate_hash(model['path'])
        
        if hash_value:
            # Update model with hash
            model['hash'] = hash_value
            db_manager.upsert_model(model)
            
            return jsonify({
                'status': 'success',
                'hash': hash_value
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate hash'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get model collection statistics"""
    try:
        stats = db_manager.get_statistics()
        
        return jsonify({
            'status': 'success',
            'statistics': stats
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@models_bp.route('/types', methods=['GET'])
def get_model_types():
    """Get available model types and their counts"""
    try:
        stats = db_manager.get_statistics()
        
        return jsonify({
            'status': 'success',
            'types': stats.get('by_type', {}),
            'total': stats.get('total_models', 0)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500