"""
ComfyUI Model Explorer - File Scanner Service
Handles scanning directories for AI models and extracting metadata
"""

import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

class ModelFile:
    """Represents a single model file with metadata"""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.name = self.file_path.stem
        self.extension = self.file_path.suffix.lower()
        self.full_path = str(self.file_path.absolute())
        
        # Extract metadata
        self._extract_metadata()
        self._detect_model_type()
        self._find_notes_file()
    
    def _extract_metadata(self):
        """Extract file metadata like size, dates"""
        try:
            stat = self.file_path.stat()
            self.size_bytes = stat.st_size
            self.size_formatted = self._format_file_size(stat.st_size)
            self.created = datetime.fromtimestamp(stat.st_ctime).isoformat()
            self.modified = datetime.fromtimestamp(stat.st_mtime).isoformat()
            self.format = self._detect_format()
        except (OSError, FileNotFoundError):
            self.size_bytes = 0
            self.size_formatted = "Unknown"
            self.created = "Unknown"
            self.modified = "Unknown"
            self.format = "Unknown"
    
    def _detect_format(self) -> str:
        """Detect the model file format"""
        format_map = {
            '.safetensors': 'SafeTensors',
            '.ckpt': 'Checkpoint',
            '.pt': 'PyTorch',
            '.pth': 'PyTorch',
            '.bin': 'Binary'
        }
        return format_map.get(self.extension, 'Unknown')
    
    def _detect_model_type(self):
        """Detect model type based on filename and path patterns"""
        filename_lower = self.name.lower()
        path_lower = str(self.file_path.parent).lower()
        
        # Define model type patterns
        type_patterns = {
            'checkpoint': [
                'xl', 'sd15', 'sd21', 'base', 'realistic', 'dream', 'photo',
                'portrait', 'anime', 'cartoon', 'art', 'style', 'mix'
            ],
            'lora': [
                'lora', 'lycoris', 'locon', 'loha', 'lokr', 'oft'
            ],
            'vae': [
                'vae', 'autoencoder', 'clear', 'blessed', 'anime'
            ],
            'controlnet': [
                'controlnet', 'control', 'canny', 'depth', 'openpose', 
                'scribble', 'seg', 'normal', 'lineart', 'mlsd'
            ],
            'embedding': [
                'embedding', 'textual_inversion', 'ti', 'negative'
            ]
        }
        
        # Check directory structure first
        if 'checkpoint' in path_lower:
            self.type = 'Checkpoint'
        elif 'lora' in path_lower:
            self.type = 'LoRA' 
        elif 'vae' in path_lower:
            self.type = 'VAE'
        elif 'controlnet' in path_lower:
            self.type = 'ControlNet'
        elif 'embedding' in path_lower or 'textual_inversion' in path_lower:
            self.type = 'Embedding'
        else:
            # Fallback to filename pattern matching
            detected_type = None
            max_matches = 0
            
            for model_type, patterns in type_patterns.items():
                matches = sum(1 for pattern in patterns if pattern in filename_lower)
                if matches > max_matches:
                    max_matches = matches
                    detected_type = model_type
            
            if detected_type:
                self.type = detected_type.title()
            else:
                # Default based on file size (rough heuristic)
                if self.size_bytes > 2_000_000_000:  # > 2GB likely checkpoint
                    self.type = 'Checkpoint'
                elif self.size_bytes > 500_000_000:  # > 500MB likely LoRA or VAE
                    self.type = 'LoRA'
                else:
                    self.type = 'Unknown'
    
    def _find_notes_file(self):
        """Find companion .txt file with notes"""
        possible_notes = [
            self.file_path.with_suffix('.txt'),
            self.file_path.parent / f"{self.name}.txt",
            self.file_path.parent / f"{self.name} - notes.txt",
            self.file_path.parent / f"{self.name} - readme.txt",
            self.file_path.parent / "readme.txt"
        ]
        
        self.notes_file = None
        self.notes = ""
        self.has_notes = False
        
        for notes_path in possible_notes:
            if notes_path.exists():
                self.notes_file = str(notes_path)
                self.has_notes = True
                try:
                    with open(notes_path, 'r', encoding='utf-8', errors='ignore') as f:
                        self.notes = f.read().strip()
                    break
                except (OSError, UnicodeDecodeError):
                    continue
    
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
    
    def get_hash(self, algorithm='sha256') -> Optional[str]:
        """Generate file hash (expensive operation, use sparingly)"""
        try:
            hash_obj = hashlib.new(algorithm)
            with open(self.file_path, 'rb') as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except (OSError, ValueError):
            return None
    
    def _generate_stable_id(self) -> str:
        """Generate a stable string-based ID from file path"""
        # Use a hash of the full path to create a stable, unique string ID
        # This avoids JavaScript number precision issues
        path_bytes = self.full_path.encode('utf-8')
        hash_obj = hashlib.md5(path_bytes)
        return hash_obj.hexdigest()[:16]  # 16-character hex string
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self._generate_stable_id(),  # Use string-based ID instead of hash(path)
            'name': self.name,
            'type': self.type,
            'size': self.size_formatted,
            'size_bytes': self.size_bytes,
            'format': self.format,
            'base_model': self._detect_base_model(),
            'created': self.created,
            'modified': self.modified,
            'path': self.full_path,
            'has_notes': self.has_notes,
            'notes': self.notes,
            'examples': []  # Placeholder for future image examples
        }
    
    def _detect_base_model(self) -> str:
        """Attempt to detect base model from filename"""
        filename_lower = self.name.lower()
        
        if any(x in filename_lower for x in ['xl', 'sdxl']):
            return 'SDXL'
        elif any(x in filename_lower for x in ['sd21', 'sd_21', '2.1']):
            return 'SD 2.1'
        elif any(x in filename_lower for x in ['sd15', 'sd_15', '1.5']):
            return 'SD 1.5'
        else:
            return 'Unknown'


class FileScanner:
    """Scans directories for AI model files"""
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.safetensors': 'safetensors',
        '.ckpt': 'checkpoint', 
        '.pt': 'pytorch',
        '.pth': 'pytorch',
        '.bin': 'binary'
    }
    
    def __init__(self, progress_callback=None):
        """
        Initialize scanner
        
        Args:
            progress_callback: Optional function to call with progress updates
        """
        self.progress_callback = progress_callback
        self.scanned_models = []
    
    def scan_directory(self, root_path: str, recursive: bool = True) -> List[ModelFile]:
        """
        Scan directory for model files
        
        Args:
            root_path: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            List of ModelFile objects
        """
        if not os.path.exists(root_path):
            raise FileNotFoundError(f"Directory not found: {root_path}")
        
        self.scanned_models = []
        root_path = Path(root_path)
        
        # Count total files for progress tracking
        if self.progress_callback:
            total_files = self._count_model_files(root_path, recursive)
            processed = 0
        
        # Scan for model files
        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"
            
        for file_path in root_path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                try:
                    model = ModelFile(str(file_path))
                    self.scanned_models.append(model)
                    
                    if self.progress_callback:
                        processed += 1
                        self.progress_callback(processed, total_files, model.name)
                        
                except Exception as e:
                    print(f"Warning: Failed to process {file_path}: {e}")
                    continue
        
        return self.scanned_models
    
    def _count_model_files(self, root_path: Path, recursive: bool) -> int:
        """Count total model files for progress tracking"""
        count = 0
        try:
            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"
                
            for file_path in root_path.glob(pattern):
                if file_path.is_file() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                    count += 1
        except Exception:
            return 0
        return count
    
    def get_models_as_dict(self) -> List[Dict]:
        """Get scanned models as list of dictionaries"""
        return [model.to_dict() for model in self.scanned_models]
    
    def filter_models(self, models: List[Dict], 
                     search_term: str = "", 
                     model_type: str = "all") -> List[Dict]:
        """
        Filter models based on search and type criteria
        
        Args:
            models: List of model dictionaries
            search_term: Search string to match against name/notes
            model_type: Model type filter ('all', 'checkpoint', 'lora', etc.)
            
        Returns:
            Filtered list of models
        """
        filtered = models
        
        # Apply search filter
        if search_term:
            search_lower = search_term.lower()
            filtered = [
                model for model in filtered
                if search_lower in model['name'].lower() 
                or search_lower in model['type'].lower()
                or search_lower in model.get('notes', '').lower()
            ]
        
        # Apply type filter
        if model_type and model_type.lower() != 'all':
            filtered = [
                model for model in filtered
                if model['type'].lower() == model_type.lower()
            ]
        
        return filtered


# Utility functions for common operations
def quick_scan(directory: str) -> Tuple[List[Dict], Dict]:
    """
    Quick scan function that returns models and summary stats
    
    Args:
        directory: Directory to scan
        
    Returns:
        Tuple of (models_list, stats_dict)
    """
    scanner = FileScanner()
    models = scanner.scan_directory(directory)
    models_dict = scanner.get_models_as_dict()
    
    # Generate summary stats
    stats = {
        'total_models': len(models_dict),
        'by_type': {},
        'with_notes': sum(1 for m in models_dict if m['has_notes']),
        'total_size_gb': sum(m['size_bytes'] for m in models_dict) / (1024**3)
    }
    
    # Count by type
    for model in models_dict:
        model_type = model['type']
        stats['by_type'][model_type] = stats['by_type'].get(model_type, 0) + 1
    
    return models_dict, stats


# Test function for development
def test_scanner():
    """Test the scanner with a sample directory"""
    import tempfile
    
    # Create test directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create sample files
        (temp_path / "test_checkpoint.safetensors").touch()
        (temp_path / "loras").mkdir()
        (temp_path / "loras" / "test_lora.safetensors").touch()
        
        # Test scanning
        scanner = FileScanner()
        models = scanner.scan_directory(temp_dir)
        
        print(f"Found {len(models)} test models:")
        for model in models:
            print(f"  - {model.name} ({model.type}) ID: {model._generate_stable_id()}")
        
        return models


if __name__ == "__main__":
    # Run test if executed directly
    test_scanner()