"""
File-based cache for project analysis results and file hashes.
Supports incremental updates by tracking file changes via content hashing.
"""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Set


class FileHashCache:
    """Tracks file hashes for detecting changes in a project."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of a file's content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except (IOError, OSError):
            return ""
    
    def compute_directory_hashes(self) -> Dict[str, str]:
        """Compute hashes for all Python files in the project."""
        hashes = {}
        for py_file in self.project_path.rglob("*.py"):
            # Skip common non-essential directories
            if any(part.startswith('.') for part in py_file.parts):
                continue
            if 'venv' in py_file.parts or '__pycache__' in py_file.parts:
                continue
            
            rel_path = str(py_file.relative_to(self.project_path))
            hashes[rel_path] = self.compute_file_hash(str(py_file))
        
        return hashes
    
    def get_changed_files(self, old_hashes: Dict[str, str]) -> tuple:
        """Compare current file hashes with old ones and return (added, modified, deleted) files."""
        current_hashes = self.compute_directory_hashes()
        
        added = set(current_hashes.keys()) - set(old_hashes.keys())
        modified = set()
        for path in set(current_hashes.keys()) & set(old_hashes.keys()):
            if current_hashes[path] != old_hashes[path]:
                modified.add(path)
        deleted = set(old_hashes.keys()) - set(current_hashes.keys())
        
        return added, modified, deleted


class AnalysisCache:
    """Persistent cache for storing and retrieving analysis results."""
    
    CACHE_DIR_NAME = ".chronos_cache"
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.cache_dir = self.project_path / self.CACHE_DIR_NAME
        self.hashes_file = self.cache_dir / "file_hashes.json"
        self.results_file = self.cache_dir / "latest_result.json"
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(exist_ok=True)
    
    def is_valid(self) -> bool:
        """Check if valid cached results exist."""
        return self.results_file.exists() and self.hashes_file.exists()
    
    def get_cached_hashes(self) -> Dict[str, str]:
        """Load previously stored file hashes."""
        if not self.hashes_file.exists():
            return {}
        
        try:
            with open(self.hashes_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def get_cached_result(self) -> Optional[Dict[str, Any]]:
        """Load previously stored analysis result."""
        if not self.results_file.exists():
            return None
        
        try:
            with open(self.results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
    
    def save_result(self, result: Dict[str, Any]) -> None:
        """Save analysis result to cache."""
        self.results_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def save_hashes(self, hashes: Dict[str, str]) -> None:
        """Save current file hashes."""
        self.hashes_file.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def invalidate(self) -> None:
        """Invalidate and remove all cache for a project."""
        if self.results_file.exists():
            self.results_file.unlink()
        if self.hashes_file.exists():
            self.hashes_file.unlink()
    
    def needs_update(self, current_hashes: Dict[str, str]) -> tuple:
        """
        Check if the cache is stale.
        Returns (needs_update: bool, changed_files: set).
        """
        cached_hashes = self.get_cached_hashes()
        if not cached_hashes:
            return True, set()  # No cache → full update needed
        
        # Compare hashes
        changed = set()
        for path in set(current_hashes.keys()) | set(cached_hashes.keys()):
            current_hash = current_hashes.get(path, "")
            cached_hash = cached_hashes.get(path, "")
            
            if current_hash != cached_hash:
                if current_hash and cached_hash:
                    changed.add(("modified", path))  # File was modified
                elif current_hash:
                    changed.add(("added", path))     # New file
                else:
                    changed.add(("deleted", path))    # Deleted file
        
        return len(changed) > 0, changed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.cache_dir.exists():
            return {"exists": False}
        
        files = list(self.cache_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        return {
            "exists": True,
            "files_count": len(files),
            "total_size_bytes": total_size,
            "cached_at": datetime.fromtimestamp(self.results_file.stat().st_mtime).isoformat() if self.results_file.exists() else None
        }


def get_project_cache(project_path: str) -> AnalysisCache:
    """Factory function to create a cache instance for a project."""
    return AnalysisCache(project_path)