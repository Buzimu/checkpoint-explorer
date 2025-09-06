"""
File scanner service for discovering and cataloging AI models
"""
import os
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple
from dataclasses import dataclass, asdict

from backend.config import Config
from backend.database import db_manager

logger = logging.getLogger(__name__)


@dataclass
class ModelFile:
    """Data class representing a model file"""
    id: str
    name: str
    type: str
    path: str
    size_bytes: int
    size_formatted: str
    format: str
    base_model: str
    created_at: str
    modified_at: str
    has_notes: bool = False
    notes_content: str = ""
    hash: Optional[str] = None
    metadata: Optional[Dict] = None


class FileScannerService:
    """Service for scanning directories and discovering AI models"""
    
    def __init__(self, db_manager=None):
        """
        Initialize scanner service
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager or globals()['db_manager']
        self.supported_extensions = Config.SUPPORTED_EXTENSIONS
        self.type_patterns = Config.MODEL_TYPE_PATTERNS
        self.progress_callback: Optional[Callable] = None
        self.scan_errors: List[str] = []
    
    def scan_directory(self, 
                      directory: str, 
                      recursive: bool = True,
                      progress_callback: Optional[Callable] = None) -> Tuple[List[ModelFile], Dict]:
        """
        Scan directory for model files
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories
            progress_callback: Callback function for progress updates
            
        Returns:
            Tuple of (list of ModelFile objects, statistics dict)
        """
        logger.info(f"Starting scan of directory: {directory}")
        
        if not os.path.exists(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        self.progress_callback = progress_callback
        self.scan_errors = []
        
        # Start scan record in database
        scan_id = self.db.start_scan(directory)
        
        # Get existing models from database for this directory
        existing_models = {m['path']: m for m in self.db.get_all_models()}
        
        # Scan for new models
        discovered_models = []
        directory_path = Path(directory)
        
        # Count total files for progress
        total_files = self._count_model_files(directory_path, recursive)
        processed = 0
        
        # Scan pattern
        pattern = "**/*" if recursive else "*"
        
        for file_path in directory_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                try:
                    model = self._process_model_file(file_path)
                    discovered_models.append(model)
                    
                    processed += 1
                    if self.progress_callback:
                        self.progress_callback(processed, total_files, model.name)
                    
                except Exception as e:
                    error_msg = f"Failed to process {file_path}: {str(e)}"
                    logger.error(error_msg)
                    self.scan_errors.append(error_msg)
        
        # Calculate statistics
        stats = self._calculate_scan_stats(discovered_models, existing_models)
        
        # Update database
        self._update_database(discovered_models, existing_models, directory)
        
        # Complete scan record
        self.db.complete_scan(scan_id, stats, self.scan_errors)
        
        logger.info(f"Scan completed: {stats}")
        
        return discovered_models, stats
    
    def _process_model_file(self, file_path: Path) -> ModelFile:
        """Process a single model file"""
        stat = file_path.stat()
        
        model = ModelFile(
            id=self._generate_id(str(file_path)),
            name=file_path.stem,
            type=self._detect_model_type(file_path),
            path=str(file_path.absolute()),
            size_bytes=stat.st_size,
            size_formatted=self._format_file_size(stat.st_size),
            format=self.supported_extensions.get(file_path.suffix.lower(), 'Unknown'),
            base_model=self._detect_base_model(file_path.stem),
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat()
        )
        
        # Check for notes file
        notes_content = self._find_notes_file(file_path)
        if notes_content:
            model.has_notes = True
            model.notes_content = notes_content
        
        # Extract additional metadata
        model.metadata = self._extract_metadata(file_path)
        
        return model
    
    def _detect_model_type(self, file_path: Path) -> str:
        """Detect model type based on path and filename patterns"""
        filename_lower = file_path.stem.lower()
        path_lower = str(file_path.parent).lower()
        
        # Check directory structure first
        for model_type in ['checkpoint', 'lora', 'vae', 'controlnet', 'embedding']:
            if model_type in path_lower:
                return model_type.title()
        
        # Check filename patterns
        detected_type = None
        max_matches = 0
        
        for model_type, patterns in self.type_patterns.items():
            matches = sum(1 for pattern in patterns if pattern in filename_lower)
            if matches > max_matches:
                max_matches = matches
                detected_type = model_type
        
        if detected_type:
            return detected_type.title()
        
        # Heuristic based on file size
        size_bytes = file_path.stat().st_size
        if size_bytes > 2_000_000_000:  # > 2GB
            return 'Checkpoint'
        elif size_bytes > 500_000_000:  # > 500MB
            return 'LoRA'
        else:
            return 'Unknown'
    
    def _detect_base_model(self, filename: str) -> str:
        """Detect base model from filename"""
        filename_lower = filename.lower()
        
        if any(x in filename_lower for x in ['xl', 'sdxl']):
            return 'SDXL'
        elif any(x in filename_lower for x in ['sd21', 'sd_21', '2.1']):
            return 'SD 2.1'
        elif any(x in filename_lower for x in ['sd15', 'sd_15', '1.5']):
            return 'SD 1.5'
        elif any(x in filename_lower for x in ['flux']):
            return 'Flux'
        else:
            return 'Unknown'
    
    def _find_notes_file(self, model_path: Path) -> Optional[str]:
        """Find and read companion notes file"""
        possible_notes = [
            model_path.with_suffix('.txt'),
            model_path.parent / f"{model_path.stem}.txt",
            model_path.parent / f"{model_path.stem} - notes.txt",
            model_path.parent / f"{model_path.stem} - readme.txt",
        ]
        
        for notes_path in possible_notes:
            if notes_path.exists():
                try:
                    with open(notes_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read().strip()
                except Exception as e:
                    logger.warning(f"Failed to read notes file {notes_path}: {e}")
        
        return None
    
    def _extract_metadata(self, file_path: Path) -> Dict:
        """Extract additional metadata from model file"""
        metadata = {
            'file_extension': file_path.suffix.lower(),
            'parent_directory': file_path.parent.name,
            'full_path': str(file_path.absolute()),
        }
        
        # Could add more metadata extraction here (e.g., from safetensors headers)
        
        return metadata
    
    def _generate_id(self, file_path: str) -> str:
        """Generate stable ID for model"""
        path_bytes = file_path.encode('utf-8')
        hash_obj = hashlib.md5(path_bytes)
        return hash_obj.hexdigest()[:16]
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        import math
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_names[i]}"
    
    def _count_model_files(self, directory: Path, recursive: bool) -> int:
        """Count total model files for progress tracking"""
        count = 0
        pattern = "**/*" if recursive else "*"
        
        try:
            for file_path in directory.glob(pattern):
                if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                    count += 1
        except Exception as e:
            logger.warning(f"Error counting files: {e}")
            return 0
        
        return count
    
    def _calculate_scan_stats(self, discovered: List[ModelFile], existing: Dict) -> Dict:
        """Calculate scan statistics"""
        discovered_paths = {m.path for m in discovered}
        existing_paths = set(existing.keys())
        
        added = discovered_paths - existing_paths
        updated = discovered_paths & existing_paths
        removed = existing_paths - discovered_paths
        
        stats = {
            'found': len(discovered),
            'added': len(added),
            'updated': len(updated),
            'removed': len(removed),
            'by_type': {}
        }
        
        # Count by type
        for model in discovered:
            model_type = model.type
            stats['by_type'][model_type] = stats['by_type'].get(model_type, 0) + 1
        
        # Calculate total size
        stats['total_size_bytes'] = sum(m.size_bytes for m in discovered)
        stats['total_size_gb'] = round(stats['total_size_bytes'] / (1024**3), 2)
        
        return stats
    
    def _update_database(self, discovered: List[ModelFile], existing: Dict, directory: str):
        """Update database with scan results"""
        discovered_paths = {m.path: m for m in discovered}
        
        # Add or update discovered models
        for model in discovered:
            model_dict = asdict(model)
            self.db.upsert_model(model_dict)
        
        # Mark removed models (those in the scanned directory but not found)
        directory_path = Path(directory)
        for path, existing_model in existing.items():
            if (directory_path in Path(path).parents or Path(path).parent == directory_path) \
               and path not in discovered_paths:
                # Model was removed - you might want to delete or mark as removed
                logger.info(f"Model removed: {path}")
                # Optionally: self.db.delete_model(existing_model['id'])
    
    def generate_hash(self, file_path: str, algorithm: str = 'sha256') -> Optional[str]:
        """
        Generate hash for a model file (expensive operation)
        
        Args:
            file_path: Path to the model file
            algorithm: Hash algorithm to use
            
        Returns:
            Hash string or None if error
        """
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate hash for {file_path}: {e}")
            return None


# Create global service instance
file_scanner = FileScannerService()