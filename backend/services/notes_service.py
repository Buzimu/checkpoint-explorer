"""
Notes management service for model documentation
"""
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import Config
from backend.database import db_manager

logger = logging.getLogger(__name__)


class NotesService:
    """Service for managing model notes with templates and versioning"""
    
    # Note templates for different model types
    TEMPLATES = {
        'checkpoint': '''# {model_name}

## Model Information
- **Type:** Checkpoint Model
- **Base Model:** {base_model}
- **File Size:** {file_size}
- **Format:** {format}

## Recommended Settings
- **Sampler:** DPM++ 2M Karras
- **Steps:** 20-30
- **CFG Scale:** 7-9
- **Clip Skip:** 1-2
- **Resolution:** 512x512 / 768x768 / 1024x1024

## Usage Notes
- **Best for:** [Describe what this model excels at]
- **Style:** [Artistic style or theme]
- **Trigger Words:** [Any specific trigger words]

## Quality Assessment
- **Overall Quality:** ⭐⭐⭐⭐⭐
- **Consistency:** ⭐⭐⭐⭐⭐
- **Flexibility:** ⭐⭐⭐⭐⭐

## Personal Notes
[Your observations and tips here]

---
*Last updated: {date}*''',

        'lora': '''# {model_name}

## Model Information
- **Type:** LoRA (Low-Rank Adaptation)
- **Base Model:** {base_model}
- **File Size:** {file_size}
- **Format:** {format}

## Usage Instructions
- **Trigger Words:** [Required trigger words]
- **Recommended Weight:** 0.7-0.8
- **Compatible Checkpoints:** [List compatible models]

## Best Practices
- **Optimal Settings:** [Your preferred settings]
- **Common Issues:** [Known problems and solutions]
- **Tips:** [Usage tips]

## Example Prompts
```
[Add successful prompt examples]
```

## Personal Rating
- **Quality:** ⭐⭐⭐⭐⭐
- **Versatility:** ⭐⭐⭐⭐⭐
- **Ease of Use:** ⭐⭐⭐⭐⭐

---
*Last updated: {date}*''',

        'vae': '''# {model_name}

## Model Information
- **Type:** VAE (Variational Autoencoder)
- **Compatible with:** {base_model}
- **File Size:** {file_size}

## Purpose & Effects
- **Improves:** [Color accuracy, detail, contrast, etc.]
- **Best for:** [Types of images this VAE enhances]
- **Comparison:** [How it compares to other VAEs]

## Technical Details
- **Performance Impact:** [VRAM usage, speed impact]
- **Known Issues:** [Any compatibility problems]

## My Experience
[Your observations and comparisons]

---
*Last updated: {date}*''',

        'controlnet': '''# {model_name}

## Model Information
- **Type:** ControlNet
- **Control Type:** [Canny, Depth, OpenPose, etc.]
- **Base Model:** {base_model}
- **File Size:** {file_size}

## Usage Settings
- **Control Weight:** 0.8-1.2
- **Starting Step:** 0
- **Ending Step:** 1.0
- **Preprocessor:** [Required preprocessor]

## Applications
- **Best Use Cases:** [Ideal scenarios]
- **Limitations:** [What it doesn't do well]

## Tips & Tricks
[Your usage tips and techniques]

---
*Last updated: {date}*''',

        'embedding': '''# {model_name}

## Model Information
- **Type:** Textual Inversion / Embedding
- **Base Model:** {base_model}
- **File Size:** {file_size}

## Usage
- **Trigger Word:** `{model_name}`
- **Placement:** [Beginning, middle, or end of prompt]
- **Weight:** Usually 1.0

## Effect Description
[What this embedding does/creates]

## Example Usage
```
[Example prompts using this embedding]
```

---
*Last updated: {date}*'''
    }
    
    def __init__(self, db_manager=None):
        """
        Initialize notes service
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager or globals()['db_manager']
        self.backup_dir = Config.BACKUP_DIR
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def get_notes(self, model_id: str) -> Dict:
        """
        Get notes for a specific model
        
        Args:
            model_id: Model identifier
            
        Returns:
            Dictionary with notes data
        """
        try:
            model = self.db.get_model(model_id)
            
            if not model:
                return {
                    'status': 'error',
                    'message': 'Model not found',
                    'content': '',
                    'has_notes': False
                }
            
            # Try to load from file system first (for compatibility)
            file_notes = self._load_from_file(model['path'])
            
            # Use database notes if no file notes
            notes_content = file_notes or model.get('notes_content', '')
            
            return {
                'status': 'success',
                'content': notes_content,
                'has_notes': bool(notes_content.strip()),
                'model_id': model_id,
                'model_name': model['name'],
                'model_type': model['type'],
                'last_modified': model.get('modified_at'),
                'word_count': len(notes_content.split()) if notes_content else 0,
                'char_count': len(notes_content) if notes_content else 0,
                'templates': self.get_available_templates(),
                'backups': self.get_backups(model_id)
            }
            
        except Exception as e:
            logger.error(f"Failed to get notes for {model_id}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'content': '',
                'has_notes': False
            }
    
    def save_notes(self, model_id: str, content: str, create_backup: bool = True) -> Dict:
        """
        Save notes for a specific model
        
        Args:
            model_id: Model identifier
            content: Notes content
            create_backup: Whether to create a backup
            
        Returns:
            Result dictionary
        """
        try:
            model = self.db.get_model(model_id)
            
            if not model:
                return {
                    'status': 'error',
                    'message': 'Model not found'
                }
            
            # Create backup if requested
            if create_backup and model.get('notes_content'):
                self._create_backup(model_id, model['notes_content'])
            
            # Save to database
            success = self.db.update_model_notes(model_id, content)
            
            # Also save to file system for compatibility
            self._save_to_file(model['path'], content)
            
            if success:
                return {
                    'status': 'success',
                    'message': 'Notes saved successfully',
                    'model_id': model_id,
                    'word_count': len(content.split()) if content else 0,
                    'char_count': len(content),
                    'saved_at': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to save notes to database'
                }
            
        except Exception as e:
            logger.error(f"Failed to save notes for {model_id}: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_template(self, template_type: str, model_data: Dict = None) -> str:
        """
        Get a formatted template for a specific model type
        
        Args:
            template_type: Type of template
            model_data: Model data for template variables
            
        Returns:
            Formatted template string
        """
        template = self.TEMPLATES.get(template_type.lower(), self.TEMPLATES['checkpoint'])
        
        # Default values
        values = {
            'model_name': 'Model Name',
            'base_model': 'Unknown',
            'file_size': 'Unknown',
            'format': 'Unknown',
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Update with actual model data if provided
        if model_data:
            values.update({
                'model_name': model_data.get('name', 'Model Name'),
                'base_model': model_data.get('base_model', 'Unknown'),
                'file_size': model_data.get('size_formatted', 'Unknown'),
                'format': model_data.get('format', 'Unknown')
            })
        
        return template.format(**values)
    
    def get_available_templates(self) -> List[Dict]:
        """Get list of available note templates"""
        return [
            {
                'id': 'checkpoint',
                'name': 'Checkpoint Model',
                'description': 'Full model checkpoint template'
            },
            {
                'id': 'lora',
                'name': 'LoRA Model',
                'description': 'LoRA adaptation template'
            },
            {
                'id': 'vae',
                'name': 'VAE Model',
                'description': 'VAE encoder template'
            },
            {
                'id': 'controlnet',
                'name': 'ControlNet',
                'description': 'ControlNet model template'
            },
            {
                'id': 'embedding',
                'name': 'Embedding',
                'description': 'Textual inversion template'
            }
        ]
    
    def _create_backup(self, model_id: str, content: str):
        """Create a backup of notes"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{model_id}_backup_{timestamp}.txt"
            backup_path = self.backup_dir / backup_filename
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Created backup: {backup_path}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
    
    def get_backups(self, model_id: str) -> List[Dict]:
        """Get available backups for a model"""
        backups = []
        
        try:
            # Get from database history
            history = self.db.get_notes_history(model_id)
            
            for entry in history:
                backups.append({
                    'id': entry['id'],
                    'created_at': entry['created_at'],
                    'content_preview': entry['content'][:100] if entry['content'] else '',
                    'source': 'database'
                })
            
            # Also check file system backups
            pattern = f"{model_id}_backup_*.txt"
            for backup_file in self.backup_dir.glob(pattern):
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'size': stat.st_size,
                    'source': 'file'
                })
            
            # Sort by creation time, newest first
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to get backups: {e}")
        
        return backups[:10]  # Return only last 10 backups
    
    def restore_backup(self, model_id: str, backup_id: str = None, backup_filename: str = None) -> Dict:
        """
        Restore a backup for a model
        
        Args:
            model_id: Model identifier
            backup_id: Database backup ID
            backup_filename: File system backup filename
            
        Returns:
            Result dictionary
        """
        try:
            content = None
            
            # Restore from database history
            if backup_id:
                history = self.db.get_notes_history(model_id, limit=50)
                for entry in history:
                    if str(entry['id']) == str(backup_id):
                        content = entry['content']
                        break
            
            # Restore from file system
            elif backup_filename:
                backup_path = self.backup_dir / backup_filename
                if backup_path.exists():
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        content = f.read()
            
            if content is not None:
                # Save the restored content
                return self.save_notes(model_id, content, create_backup=True)
            else:
                return {
                    'status': 'error',
                    'message': 'Backup not found'
                }
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _load_from_file(self, model_path: str) -> Optional[str]:
        """Load notes from companion text file"""
        try:
            model_path = Path(model_path)
            notes_path = model_path.with_suffix('.txt')
            
            if notes_path.exists():
                with open(notes_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read().strip()
        except Exception as e:
            logger.warning(f"Failed to load notes from file: {e}")
        
        return None
    
    def _save_to_file(self, model_path: str, content: str):
        """Save notes to companion text file"""
        try:
            model_path = Path(model_path)
            notes_path = model_path.with_suffix('.txt')
            
            with open(notes_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Saved notes to file: {notes_path}")
            
        except Exception as e:
            logger.warning(f"Failed to save notes to file: {e}")
    
    def export_all_notes(self) -> Dict:
        """Export all notes for backup or migration"""
        try:
            models = self.db.get_all_models({'has_notes': True})
            
            export_data = {
                'version': '1.0',
                'exported_at': datetime.utcnow().isoformat(),
                'notes': []
            }
            
            for model in models:
                if model.get('notes_content'):
                    export_data['notes'].append({
                        'model_id': model['id'],
                        'model_name': model['name'],
                        'model_path': model['path'],
                        'content': model['notes_content'],
                        'last_modified': model.get('modified_at')
                    })
            
            return {
                'status': 'success',
                'data': export_data,
                'count': len(export_data['notes'])
            }
            
        except Exception as e:
            logger.error(f"Failed to export notes: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }


# Create global service instance
notes_service = NotesService()