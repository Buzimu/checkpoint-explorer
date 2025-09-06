"""
ComfyUI Model Explorer Backend Package
"""

__version__ = '2.0.0'
__author__ = 'ComfyUI Model Explorer Team'

# Make key components easily importable
from backend.app import create_app
from backend.config import Config

__all__ = ['create_app', 'Config']