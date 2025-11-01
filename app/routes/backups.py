"""
API endpoint for backup management
"""
from flask import Blueprint, jsonify, request
from app.services.database import get_backup_info, restore_from_backup

bp = Blueprint('backups', __name__)


@bp.route('/backups', methods=['GET'])
def list_backups():
    """Get list of available backups"""
    try:
        backups = get_backup_info()
        return jsonify({
            'success': True,
            'backups': backups,
            'count': len(backups)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/backups/restore', methods=['POST'])
def restore_backup():
    """Restore database from a backup"""
    try:
        data = request.json
        backup_filename = data.get('filename')
        
        if not backup_filename:
            return jsonify({
                'success': False,
                'error': 'Missing backup filename'
            }), 400
        
        success = restore_from_backup(backup_filename)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Database restored from {backup_filename}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore backup'
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500