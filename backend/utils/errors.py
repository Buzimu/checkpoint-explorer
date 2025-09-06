"""
Error handling utilities
"""
import logging
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """
    Register global error handlers for the Flask app
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handle bad request errors"""
        return jsonify({
            'status': 'error',
            'message': 'Bad request',
            'details': str(error)
        }), 400
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle not found errors"""
        return jsonify({
            'status': 'error',
            'message': 'Resource not found',
            'path': request.path
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle method not allowed errors"""
        return jsonify({
            'status': 'error',
            'message': 'Method not allowed',
            'method': request.method,
            'path': request.path
        }), 405
    
    @app.errorhandler(409)
    def conflict(error):
        """Handle conflict errors"""
        return jsonify({
            'status': 'error',
            'message': 'Conflict',
            'details': str(error)
        }), 409
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal error: {error}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'details': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle all HTTP exceptions"""
        return jsonify({
            'status': 'error',
            'message': error.description,
            'code': error.code
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle unexpected errors"""
        logger.error(f"Unexpected error: {error}", exc_info=True)
        
        # Don't expose internal errors in production
        if app.config.get('DEBUG'):
            message = str(error)
        else:
            message = 'An unexpected error occurred'
        
        return jsonify({
            'status': 'error',
            'message': message
        }), 500


class APIError(Exception):
    """Custom API error class"""
    
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        """Convert error to dictionary"""
        rv = dict(self.payload or ())
        rv['message'] = self.message
        rv['status'] = 'error'
        return rv


class ValidationError(APIError):
    """Validation error"""
    
    def __init__(self, message, field=None):
        super().__init__(message, status_code=400)
        if field:
            self.payload = {'field': field}


class NotFoundError(APIError):
    """Resource not found error"""
    
    def __init__(self, message, resource=None):
        super().__init__(message, status_code=404)
        if resource:
            self.payload = {'resource': resource}


class ConflictError(APIError):
    """Conflict error"""
    
    def __init__(self, message, resource=None):
        super().__init__(message, status_code=409)
        if resource:
            self.payload = {'resource': resource}


class AuthorizationError(APIError):
    """Authorization error"""
    
    def __init__(self, message):
        super().__init__(message, status_code=403)