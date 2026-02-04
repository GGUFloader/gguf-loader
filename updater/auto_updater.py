"""
Auto Updater Module
One-click update system that downloads and applies only changed files
"""
import os
import sys
import json
import shutil
import hashlib
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import zipfile

logger = logging.getLogger(__name__)

class AutoUpdater:
    """Handles automatic updates with delta patching"""
    
    GITHUB_API_URL = "https://api.github.com/repos/GGUFloader/gguf-loader"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com/GGUFloader/gguf-loader"
    
    def __init__(self, current_version: str):
        self.current_version = current_version
        self.temp_dir = None
        self.backup_dir = None
        
    def download_update(self, version: str, progress_callback=None) -> bool:
        """
        Download and apply update
        
        Args:
            version: Version to update to (e.g., '2.1.0')
            progress_callback: Function to call with progress updates
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            if progress_callback:
                progress_callback("Preparing update...", 0)
            
            # Create temp directory
            self.temp_dir = tempfile.mkdtemp(prefix='gguf_update_')
            logger.info(f"Created temp directory: {self.temp_dir}")
            
            if progress_callback:
                progress_callback("Downloading update files...", 10)
            
            # Download the release archive
            archive_url = f"{self.GITHUB_API_URL}/zipball/v{version}"
            archive_path = self._download_archive(archive_url, version)
            
            if not archive_path:
                return False
            
            if progress_callback:
                progress_callback("Extracting files...", 40)
            
            # Extract archive
            extract_dir = self._extract_archive(archive_path)
            if not extract_dir:
                return False
            
            if progress_callback:
                progress_callback("Comparing files...", 60)
            
            # Get list of changed files
            changed_files = self._get_changed_files(extract_dir)
            
            if progress_callback:
                progress_callback(f"Updating {len(changed_files)} files...", 70)
            
            # Create backup
            self._create_backup(changed_files)
            
            if progress_callback:
                progress_callback("Applying updates...", 80)
            
            # Apply updates
            success = self._apply_updates(extract_dir, changed_files)
            
            if success:
                if progress_callback:
                    progress_callback("Update completed!", 100)
                logger.info("Update applied successfully")
                return True
            else:
                if progress_callback:
                    progress_callback("Update failed, restoring backup...", 90)
                self._restore_backup()
                return False
                
        except Exception as e:
            logger.error(f"Update failed: {e}")
            if progress_callback:
                progress_callback(f"Error: {str(e)}", -1)
            self._restore_backup()
            return False
        finally:
            self._cleanup()
    
    def _download_archive(self, url: str, version: str) -> Optional[str]:
        """Download the release archive"""
        try:
            request = Request(
                url,
                headers={'User-Agent': f'GGUF-Loader/{self.current_version}'}
            )
            
            archive_path = os.path.join(self.temp_dir, f'update_{version}.zip')
            
            with urlopen(request, timeout=30) as response:
                with open(archive_path, 'wb') as f:
                    f.write(response.read())
            
            logger.info(f"Downloaded archive to: {archive_path}")
            return archive_path
            
        except Exception as e:
            logger.error(f"Failed to download archive: {e}")
            return None
    
    def _extract_archive(self, archive_path: str) -> Optional[str]:
        """Extract the downloaded archive"""
        try:
            extract_dir = os.path.join(self.temp_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # GitHub zipball creates a subdirectory, find it
            subdirs = [d for d in os.listdir(extract_dir) 
                      if os.path.isdir(os.path.join(extract_dir, d))]
            
            if subdirs:
                actual_dir = os.path.join(extract_dir, subdirs[0])
                logger.info(f"Extracted to: {actual_dir}")
                return actual_dir
            
            return extract_dir
            
        except Exception as e:
            logger.error(f"Failed to extract archive: {e}")
            return None
    
    def _get_changed_files(self, new_dir: str) -> List[str]:
        """Compare files and get list of changed files"""
        changed = []
        current_dir = os.getcwd()
        
        # Files to exclude from updates
        exclude_patterns = [
            '__pycache__',
            '.git',
            '.vscode',
            'venv',
            'models',
            'chats',
            'exports',
            'logs',
            'cache',
            'config',
            '.pyc',
            'feedback_config.json'
        ]
        
        for root, dirs, files in os.walk(new_dir):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not any(ex in d for ex in exclude_patterns)]
            
            for file in files:
                # Skip excluded files
                if any(ex in file for ex in exclude_patterns):
                    continue
                
                new_file = os.path.join(root, file)
                rel_path = os.path.relpath(new_file, new_dir)
                current_file = os.path.join(current_dir, rel_path)
                
                # Check if file is new or changed
                if not os.path.exists(current_file):
                    changed.append(rel_path)
                    logger.info(f"New file: {rel_path}")
                elif self._file_hash(new_file) != self._file_hash(current_file):
                    changed.append(rel_path)
                    logger.info(f"Changed file: {rel_path}")
        
        return changed
    
    def _file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of a file"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _create_backup(self, files: List[str]):
        """Create backup of files that will be updated"""
        try:
            self.backup_dir = tempfile.mkdtemp(prefix='gguf_backup_')
            current_dir = os.getcwd()
            
            for rel_path in files:
                current_file = os.path.join(current_dir, rel_path)
                if os.path.exists(current_file):
                    backup_file = os.path.join(self.backup_dir, rel_path)
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    shutil.copy2(current_file, backup_file)
            
            logger.info(f"Created backup in: {self.backup_dir}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
    
    def _apply_updates(self, new_dir: str, files: List[str]) -> bool:
        """Apply the updates"""
        try:
            current_dir = os.getcwd()
            
            for rel_path in files:
                new_file = os.path.join(new_dir, rel_path)
                current_file = os.path.join(current_dir, rel_path)
                
                # Create directory if needed
                os.makedirs(os.path.dirname(current_file), exist_ok=True)
                
                # Copy new file
                shutil.copy2(new_file, current_file)
                logger.info(f"Updated: {rel_path}")
            
            # Update version in __init__.py
            self._update_version_file(new_dir)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply updates: {e}")
            return False
    
    def _update_version_file(self, new_dir: str):
        """Update the version in __init__.py"""
        try:
            new_init = os.path.join(new_dir, '__init__.py')
            current_init = os.path.join(os.getcwd(), '__init__.py')
            
            if os.path.exists(new_init):
                shutil.copy2(new_init, current_init)
                logger.info("Updated version file")
        except Exception as e:
            logger.error(f"Failed to update version file: {e}")
    
    def _restore_backup(self):
        """Restore files from backup"""
        if not self.backup_dir or not os.path.exists(self.backup_dir):
            return
        
        try:
            current_dir = os.getcwd()
            
            for root, dirs, files in os.walk(self.backup_dir):
                for file in files:
                    backup_file = os.path.join(root, file)
                    rel_path = os.path.relpath(backup_file, self.backup_dir)
                    current_file = os.path.join(current_dir, rel_path)
                    
                    shutil.copy2(backup_file, current_file)
            
            logger.info("Restored backup")
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
    
    def _cleanup(self):
        """Clean up temporary files"""
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temp directory")
            
            if self.backup_dir and os.path.exists(self.backup_dir):
                shutil.rmtree(self.backup_dir)
                logger.info("Cleaned up backup directory")
                
        except Exception as e:
            logger.error(f"Failed to cleanup: {e}")
    
    def restart_application(self):
        """Restart the application after update"""
        try:
            python = sys.executable
            script = sys.argv[0]
            
            logger.info("Restarting application...")
            
            # Start new process
            subprocess.Popen([python, script] + sys.argv[1:])
            
            # Exit current process
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Failed to restart application: {e}")
