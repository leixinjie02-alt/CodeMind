import logging
import hashlib
import os
import json
from pathlib import Path

def setup_logging(level=logging.INFO):
    """Configures the global logging format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def read_file_content(file_path: str) -> str:
    """Safely reads file content with UTF-8 encoding."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Failed to read file {file_path}: {e}")
        return ""

def get_file_hash(file_path: str) -> str:
    """Generates an MD5 hash of the file content."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception:
        return ""

class FileCache:
    """Manages a simple JSON-based cache to avoid re-parsing unchanged files."""
    
    def __init__(self, cache_path: str = ".codemind_cache.json"):
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def is_changed(self, file_path: str) -> bool:
        """Returns True if the file has changed since the last cache update."""
        current_hash = get_file_hash(file_path)
        cached_hash = self.cache.get(file_path)
        return current_hash != cached_hash

    def update(self, file_path: str):
        """Updates the cache with the current file hash."""
        self.cache[file_path] = get_file_hash(file_path)

    def save(self):
        """Persists the cache to disk."""
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")

def format_node_name(name: str) -> str:
    """Existing utility helper."""
    return name.strip()
