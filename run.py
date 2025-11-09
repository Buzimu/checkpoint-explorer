"""
ComfyUI Model Explorer - Application Entry Point
Simple server for automatic JSON management
"""
from app import create_app
from config import FLASK_CONFIG, MODELS_DIR, DB_FILE, IMAGES_DIR
import os

# Create the Flask app
app = create_app()

if __name__ == '__main__':
    print("\n🎨 ComfyUI Model Explorer - Flask Server")
    print("=" * 50)
    print(f"📂 Models Directory: {MODELS_DIR}")
    print(f"💾 Database File: {DB_FILE}")
    print(f"🖼️  Images Directory: {IMAGES_DIR}")
    print("=" * 50)
    
    # Check if database exists
    from app.services.database import load_db
    if os.path.exists(DB_FILE):
        db = load_db()
        print(f"✅ Database loaded: {len(db.get('models', {}))} models")
    else:
        print("⚠️  No database file found - will create on first save")
    
    print("\n🚀 Starting server on http://localhost:5000")
    print("Press Ctrl+C to stop\n")

    from app.services.background_scraper import get_background_scraper

    scraper = get_background_scraper()
    scraper.start()
    
    # Run the app
    app.run(**FLASK_CONFIG)