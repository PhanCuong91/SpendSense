import os
import shutil
import hashlib
import sys
from pathlib import Path

class DeepFolderSyncer:
    def __init__(self, source_dir: str, dest_dir: str, chunk_size: int = 131072):
        """
        Optimized for deep folder trees. 
        Increased chunk size to 128KB for faster hashing of larger files over USB.
        """
        self.source = self._prepare_path(source_dir)
        self.dest = self._prepare_path(dest_dir)
        self.chunk_size = chunk_size

        if not os.path.exists(self.source):
            raise ValueError(f"Source directory '{source_dir}' does not exist.")

    def _prepare_path(self, path_str: str) -> str:
        """Fixes Windows Max Path limitations (260 char limit) for deep trees."""
        abs_path = os.path.abspath(path_str)
        if sys.platform == "win32" and not abs_path.startswith("\\\\?\\"):
            return f"\\\\?\\{abs_path}"
        return abs_path

    def calculate_sha256(self, file_path: str) -> str:
        """Calculates SHA256 hash smoothly using raw OS paths."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except OSError as e:
            print(f"Error reading file for hash {file_path}: {e}")
            return ""

    def should_update(self, src_file: str, dest_file: str) -> bool:
        """Fast metadata comparison with hash fallback."""
        if not os.path.exists(dest_file):
            return True
        
        try:
            src_stat = os.stat(src_file)
            dest_stat = os.stat(dest_file)
            
            if src_stat.st_size != dest_stat.st_size:
                return True
                
            # Allow a 1-second buffer for cross-filesystem mtime differences (e.g., exFAT vs NTFS)
            if abs(src_stat.st_mtime - dest_stat.st_mtime) > 1:
                return self.calculate_sha256(src_file) != self.calculate_sha256(dest_file)
        except OSError:
            return True
            
        return False

    def _scan_directory(self, base_dir: str) -> set:
        """
        Recursively scans directory using os.scandir for maximum speed 
        and memory efficiency on deep trees. Returns a set of relative paths.
        """
        relative_paths = set()
        base_len = len(base_dir) if base_dir.endswith((os.sep, '/')) else len(base_dir) + 1

        def _recurse(current_dir):
            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        rel_path = entry.path[base_len:]
                        if entry.is_file(follow_symlinks=False):
                            relative_paths.add(rel_path)
                        elif entry.is_dir(follow_symlinks=False):
                            _recurse(entry.path)
            except PermissionError:
                print(f"Permission denied: {current_dir}")

        _recurse(base_dir)
        return relative_paths

    def sync(self, dry_run: bool = False, delete_extra: bool = True):
        print(f"Scanning source structure (Deep Tree Optimized)...")
        source_files = self._scan_directory(self.source)
        print(f"Found {len(source_files)} files in source.")

        # Phase 1: Copy new/modified files
        for rel_path in source_files:
            src_file = os.path.join(self.source, rel_path)
            dest_file = os.path.join(self.dest, rel_path)

            if self.should_update(src_file, dest_file):
                if dry_run:
                    print(f"[DRY RUN] Would update: {rel_path}")
                else:
                    print(f"Copying: {rel_path}")
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    try:
                        shutil.copy2(src_file, dest_file)
                    except OSError as e:
                        print(f"Failed to copy {rel_path}: {e}")

        # Phase 2: Handle deletions in destination
        if delete_extra and os.path.exists(self.dest):
            print(f"\nScanning destination for deletions...")
            dest_files = self._scan_directory(self.dest)
            
            # Find files that exist in Dest but no longer in Source
            extra_files = dest_files - source_files
            
            for rel_path in extra_files:
                dest_file = os.path.join(self.dest, rel_path)
                if dry_run:
                    print(f"[DRY RUN] Would delete: {rel_path}")
                else:
                    print(f"Deleting file: {rel_path}")
                    try:
                        os.remove(dest_file)
                    except OSError as e:
                        print(f"Could not delete {rel_path}: {e}")

            # Clean up empty directories bottom-up
            if not dry_run:
                self._clean_empty_dirs(self.dest)

        print("\nSynchronization task complete!")

    def _clean_empty_dirs(self, target_dir: str):
        """Cleans empty directories recursively from the bottom up."""
        for root, dirs, files in os.walk(target_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        os.rmdir(dir_path)
                        print(f"Removed empty directory: {dir_path}")
                except OSError:
                    pass


# --- Run Configuration ---
if __name__ == "__main__":
    # Ensure you use absolute paths or verify your exact external drive mount points
    SRC = "/Volumes/Extreme SSD/99_storage"  # Or "D:/FolderA" on Windows
    DST = "/Volumes/HDD_1/99_storage"  # Or "E:/FolderA" on Windows

    syncer = DeepFolderSyncer(SRC, DST)
    
    # 1. Run safely in dry_run mode first to verify deep path parsing
    syncer.sync(dry_run=False, delete_extra=True)
    
    # 2. Once verified, flip dry_run to False to perform actual operation
    # syncer.sync(dry_run=False, delete_extra=True)