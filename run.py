#!/usr/bin/env python
"""
ComfyUI Model Explorer - Application Entry Point
"""
import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend import create_app
from backend.config import config_dict


def setup_logging(level=logging.INFO):
    """Configure logging for the application"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log', mode='a')
        ]
    )
    
    # Reduce verbosity of some libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def main():
    """Main application entry point"""
    # Get configuration from environment
    config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Setup logging
    log_level = logging.DEBUG if config_name == 'development' else logging.INFO
    setup_logging(log_level)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Starting ComfyUI Model Explorer in {config_name} mode")
    
    # Create Flask app
    app = create_app(config_dict[config_name])
    
    # Get host and port from environment or use defaults
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5001))
    
    # Print startup information
    print("\n" + "="*60)
    print("🎨 ComfyUI Model Explorer v2.0")
    print("="*60)
    print(f"📂 Starting server on http://{host}:{port}")
    print(f"🔧 Environment: {config_name}")
    print(f"📊 Database: {app.config['DATABASE_PATH']}")
    print("\n💡 Quick Start:")
    print("   1. Open your browser to the URL above")
    print("   2. Click 'Configure Models Directory'")
    print("   3. Enter your ComfyUI models path")
    print("   4. Click 'Save & Scan Models'")
    print("\n⚡ Keyboard Shortcuts:")
    print("   • Ctrl+F: Focus search")
    print("   • F2: Edit notes for selected model")
    print("   • Escape: Clear search/close modals")
    print("   • Arrow keys: Navigate models")
    print("\n📝 Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Check if this is the first run
    from backend.config import Config
    settings = Config.get_user_settings()
    if not settings.get('models_directory'):
        print("👋 First time setup detected!")
        print("   Please configure your models directory in the web interface.\n")
    
    # Run the application
    try:
        if config_name == 'development':
            # Development mode with auto-reload
            app.run(
                host=host,
                port=port,
                debug=True,
                use_reloader=True,
                threaded=True
            )
        else:
            # Production mode
            app.run(
                host=host,
                port=port,
                debug=False,
                threaded=True
            )
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down ComfyUI Model Explorer...")
        print("   Thank you for using the application!")
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        print(f"\n❌ Error starting application: {e}")
        print("   Please check the logs for more details.")
        sys.exit(1)


if __name__ == '__main__':
    main()
