"""
Database manager for SQLite operations
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or ':memory:'
        self.init_schema()
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.db_path = app.config.get('DATABASE_PATH', ':memory:')
        self.init_schema()
    
    @contextmanager
    def get_connection(self):
        """Get database connection context manager"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = self.dict_factory
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    @staticmethod
    def dict_factory(cursor, row):
        """Convert SQLite rows to dictionaries"""
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}
    
    def init_schema(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Models table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    size_bytes INTEGER,
                    size_formatted TEXT,
                    format TEXT,
                    base_model TEXT,
                    hash TEXT,
                    created_at TEXT,
                    modified_at TEXT,
                    last_scanned TEXT,
                    metadata TEXT,
                    notes_content TEXT,
                    has_notes BOOLEAN DEFAULT 0,
                    tags TEXT,
                    rating INTEGER,
                    usage_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    civitai_model_id TEXT,
                    civitai_version_id TEXT,
                    civitai_data TEXT
                )
            ''')
            
            # Notes table for version history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notes_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT NOT NULL,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    backup_path TEXT,
                    FOREIGN KEY (model_id) REFERENCES models (id)
                )
            ''')
            
            # Tags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    color TEXT,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # Model-tags junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_tags (
                    model_id TEXT NOT NULL,
                    tag_id INTEGER NOT NULL,
                    PRIMARY KEY (model_id, tag_id),
                    FOREIGN KEY (model_id) REFERENCES models (id),
                    FOREIGN KEY (tag_id) REFERENCES tags (id)
                )
            ''')
            
            # Scan history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    directory TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    models_found INTEGER DEFAULT 0,
                    models_added INTEGER DEFAULT 0,
                    models_updated INTEGER DEFAULT 0,
                    models_removed INTEGER DEFAULT 0,
                    errors TEXT,
                    status TEXT DEFAULT 'running'
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_models_type ON models(type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_models_name ON models(name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_models_path ON models(path)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_model ON notes_history(model_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_model_tags ON model_tags(model_id)')
            
            logger.info("Database schema initialized")
    
    # Model operations
    def upsert_model(self, model_data: Dict[str, Any]) -> bool:
        """Insert or update a model"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Convert complex types to JSON strings
            if 'metadata' in model_data and isinstance(model_data['metadata'], dict):
                model_data['metadata'] = json.dumps(model_data['metadata'])
            
            if 'tags' in model_data and isinstance(model_data['tags'], list):
                model_data['tags'] = json.dumps(model_data['tags'])
            
            if 'civitai_data' in model_data and isinstance(model_data['civitai_data'], dict):
                model_data['civitai_data'] = json.dumps(model_data['civitai_data'])
            
            # Set last_scanned timestamp
            model_data['last_scanned'] = datetime.utcnow().isoformat()
            
            # Build the query dynamically
            columns = list(model_data.keys())
            placeholders = [f':{col}' for col in columns]
            
            query = f'''
                INSERT OR REPLACE INTO models ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            '''
            
            cursor.execute(query, model_data)
            return cursor.rowcount > 0
    
    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get a single model by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM models WHERE id = ?', (model_id,))
            model = cursor.fetchone()
            
            if model:
                # Parse JSON fields
                for field in ['metadata', 'tags', 'civitai_data']:
                    if field in model and model[field]:
                        try:
                            model[field] = json.loads(model[field])
                        except json.JSONDecodeError:
                            model[field] = None if field != 'tags' else []
            
            return model
    
    def get_all_models(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get all models with optional filters"""
        query = 'SELECT * FROM models WHERE 1=1'
        params = []
        
        if filters:
            if 'type' in filters and filters['type'] != 'all':
                query += ' AND type = ?'
                params.append(filters['type'])
            
            if 'search' in filters and filters['search']:
                search_term = f"%{filters['search']}%"
                query += ' AND (name LIKE ? OR notes_content LIKE ? OR tags LIKE ?)'
                params.extend([search_term, search_term, search_term])
            
            if 'has_notes' in filters:
                query += ' AND has_notes = ?'
                params.append(1 if filters['has_notes'] else 0)
        
        query += ' ORDER BY name ASC'
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            models = cursor.fetchall()
            
            # Parse JSON fields for each model
            for model in models:
                for field in ['metadata', 'tags', 'civitai_data']:
                    if field in model and model[field]:
                        try:
                            model[field] = json.loads(model[field])
                        except json.JSONDecodeError:
                            model[field] = None if field != 'tags' else []
            
            return models
    
    def delete_model(self, model_id: str) -> bool:
        """Delete a model"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM models WHERE id = ?', (model_id,))
            return cursor.rowcount > 0
    
    def update_model_notes(self, model_id: str, notes_content: str) -> bool:
        """Update model notes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Update model notes
            cursor.execute('''
                UPDATE models 
                SET notes_content = ?, has_notes = ?
                WHERE id = ?
            ''', (notes_content, bool(notes_content.strip()), model_id))
            
            # Add to notes history
            if notes_content.strip():
                cursor.execute('''
                    INSERT INTO notes_history (model_id, content, created_at)
                    VALUES (?, ?, ?)
                ''', (model_id, notes_content, datetime.utcnow().isoformat()))
            
            return cursor.rowcount > 0
    
    def get_notes_history(self, model_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get notes history for a model"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM notes_history 
                WHERE model_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (model_id, limit))
            return cursor.fetchall()
    
    # Tag operations
    def create_tag(self, name: str, color: str = None) -> int:
        """Create a new tag"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO tags (name, color, created_at)
                VALUES (?, ?, ?)
            ''', (name, color, datetime.utcnow().isoformat()))
            return cursor.lastrowid
    
    def add_model_tag(self, model_id: str, tag_name: str) -> bool:
        """Add a tag to a model"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get or create tag
            cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            tag = cursor.fetchone()
            
            if not tag:
                cursor.execute('''
                    INSERT INTO tags (name, created_at)
                    VALUES (?, ?)
                ''', (tag_name, datetime.utcnow().isoformat()))
                tag_id = cursor.lastrowid
            else:
                tag_id = tag['id']
            
            # Add model-tag relationship
            cursor.execute('''
                INSERT OR IGNORE INTO model_tags (model_id, tag_id)
                VALUES (?, ?)
            ''', (model_id, tag_id))
            
            return cursor.rowcount > 0
    
    def get_model_tags(self, model_id: str) -> List[str]:
        """Get tags for a model"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.name 
                FROM tags t
                JOIN model_tags mt ON t.id = mt.tag_id
                WHERE mt.model_id = ?
            ''', (model_id,))
            return [row['name'] for row in cursor.fetchall()]
    
    # Scan history operations
    def start_scan(self, directory: str) -> int:
        """Record the start of a scan"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO scan_history (directory, started_at, status)
                VALUES (?, ?, 'running')
            ''', (directory, datetime.utcnow().isoformat()))
            return cursor.lastrowid
    
    def complete_scan(self, scan_id: int, stats: Dict[str, int], errors: List[str] = None):
        """Record scan completion"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scan_history
                SET completed_at = ?,
                    models_found = ?,
                    models_added = ?,
                    models_updated = ?,
                    models_removed = ?,
                    errors = ?,
                    status = 'completed'
                WHERE id = ?
            ''', (
                datetime.utcnow().isoformat(),
                stats.get('found', 0),
                stats.get('added', 0),
                stats.get('updated', 0),
                stats.get('removed', 0),
                json.dumps(errors) if errors else None,
                scan_id
            ))
    
    def get_scan_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get scan history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scan_history
                ORDER BY started_at DESC
                LIMIT ?
            ''', (limit,))
            
            results = cursor.fetchall()
            for result in results:
                if result.get('errors'):
                    try:
                        result['errors'] = json.loads(result['errors'])
                    except json.JSONDecodeError:
                        result['errors'] = []
            
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total models
            cursor.execute('SELECT COUNT(*) as count FROM models')
            total_models = cursor.fetchone()['count']
            
            # Models by type
            cursor.execute('''
                SELECT type, COUNT(*) as count 
                FROM models 
                GROUP BY type
            ''')
            by_type = {row['type']: row['count'] for row in cursor.fetchall()}
            
            # Models with notes
            cursor.execute('SELECT COUNT(*) as count FROM models WHERE has_notes = 1')
            with_notes = cursor.fetchone()['count']
            
            # Total size
            cursor.execute('SELECT SUM(size_bytes) as total FROM models')
            total_size = cursor.fetchone()['total'] or 0
            
            # Most used tags
            cursor.execute('''
                SELECT t.name, COUNT(mt.model_id) as count
                FROM tags t
                JOIN model_tags mt ON t.id = mt.tag_id
                GROUP BY t.id
                ORDER BY count DESC
                LIMIT 10
            ''')
            top_tags = [{'name': row['name'], 'count': row['count']} for row in cursor.fetchall()]
            
            return {
                'total_models': total_models,
                'by_type': by_type,
                'with_notes': with_notes,
                'total_size_bytes': total_size,
                'total_size_gb': round(total_size / (1024**3), 2) if total_size else 0,
                'top_tags': top_tags
            }


# Global database manager instance
db_manager = DatabaseManager()