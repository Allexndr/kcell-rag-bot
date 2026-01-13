"""
Automatic Knowledge Base Updater - Monitors document changes and triggers reindexing
"""

import os
import json
import time
import hashlib
from pathlib import Path

class KnowledgeBaseUpdater:
    def __init__(self, docs_dir, state_file="analytics/auto_update.json", check_interval=300):
        self.docs_dir = Path(docs_dir)
        self.state_file = Path(state_file)
        self.check_interval = check_interval  # seconds
        self.last_check = 0
        self.current_state = self._load_state()

    def _load_state(self):
        """Load last known state of documents"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_state(self):
        """Save current state of documents"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_state, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving update state: {e}")

    def _calculate_file_hash(self, filepath):
        """Calculate MD5 hash of file content"""
        try:
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None

    def _get_file_info(self, filepath):
        """Get file modification time and hash"""
        try:
            stat = os.stat(filepath)
            return {
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'hash': self._calculate_file_hash(filepath)
            }
        except:
            return None

    def scan_documents(self):
        """Scan all documents and return current state"""
        current_state = {}

        # Supported file extensions
        extensions = {'.pdf', '.docx', '.txt', '.xlsx', '.pptx', '.md'}

        try:
            for root, dirs, files in os.walk(self.docs_dir):
                for file in files:
                    if Path(file).suffix.lower() in extensions:
                        filepath = Path(root) / file
                        try:
                            file_info = self._get_file_info(filepath)
                            if file_info:
                                current_state[str(filepath)] = file_info
                        except Exception as e:
                            print(f"⚠️ Error scanning {filepath}: {e}")
                            continue
        except Exception as e:
            print(f"⚠️ Error scanning documents: {e}")

        return current_state

    def check_for_changes(self):
        """Check for document changes since last scan"""
        current_time = time.time()

        # Respect check interval
        if current_time - self.last_check < self.check_interval:
            return None

        self.last_check = current_time

        print("🔍 Checking for document changes...")

        # Get current state
        new_state = self.scan_documents()

        # Compare with previous state
        changes = {
            'new_files': [],
            'deleted_files': [],
            'modified_files': [],
            'unchanged_files': []
        }

        # Find new and modified files
        for filepath, file_info in new_state.items():
            if filepath not in self.current_state:
                changes['new_files'].append(filepath)
            elif (self.current_state[filepath]['mtime'] != file_info['mtime'] or
                  self.current_state[filepath]['hash'] != file_info['hash']):
                changes['modified_files'].append(filepath)
            else:
                changes['unchanged_files'].append(filepath)

        # Find deleted files
        for filepath in self.current_state:
            if filepath not in new_state:
                changes['deleted_files'].append(filepath)

        # Update state
        self.current_state = new_state
        self._save_state()

        # Report changes
        total_changes = len(changes['new_files']) + len(changes['deleted_files']) + len(changes['modified_files'])

        if total_changes > 0:
            print(f"📁 Document changes detected:")
            print(f"  ➕ New files: {len(changes['new_files'])}")
            print(f"  ✏️ Modified files: {len(changes['modified_files'])}")
            print(f"  ➖ Deleted files: {len(changes['deleted_files'])}")
            print(f"  ✅ Unchanged files: {len(changes['unchanged_files'])}")

            return changes
        else:
            print(f"✅ No changes detected ({len(changes['unchanged_files'])} files monitored)")
            return None

    def trigger_reindexing(self, changes):
        """Trigger reindexing of changed documents"""
        if not changes:
            return

        try:
            print("🔄 Starting automatic reindexing...")

            # Import here to avoid circular imports
            import subprocess
            import sys

            # Reindex new and modified files
            files_to_reindex = changes['new_files'] + changes['modified_files']

            if files_to_reindex:
                print(f"📥 Reindexing {len(files_to_reindex)} files...")

                for filepath in files_to_reindex[:5]:  # Limit to prevent overload
                    try:
                        print(f"  🔄 Processing: {Path(filepath).name}")
                        # Call ingestion script
                        result = subprocess.run([
                            sys.executable, 'ingest_file.py', filepath
                        ], capture_output=True, text=True, timeout=60)

                        if result.returncode == 0:
                            print(f"  ✅ Successfully indexed: {Path(filepath).name}")
                        else:
                            print(f"  ❌ Failed to index: {Path(filepath).name} - {result.stderr[:100]}")

                    except subprocess.TimeoutExpired:
                        print(f"  ⏰ Timeout indexing: {Path(filepath).name}")
                    except Exception as e:
                        print(f"  ❌ Error indexing {Path(filepath).name}: {e}")

            if changes['deleted_files']:
                print(f"🗑️ Would remove {len(changes['deleted_files'])} deleted files from index")
                # In a full implementation, this would remove from vector DB

            print("✅ Auto-reindexing completed")

        except Exception as e:
            print(f"❌ Error during auto-reindexing: {e}")

    def force_full_reindex(self):
        """Force complete reindexing of all documents"""
        print("🔄 Starting full reindexing...")

        try:
            import subprocess
            import sys

            result = subprocess.run([
                sys.executable, 'ingest_all.py'
            ], capture_output=True, text=True, timeout=600)  # 10 minute timeout

            if result.returncode == 0:
                print("✅ Full reindexing completed successfully")
                # Reset state
                self.current_state = self.scan_documents()
                self._save_state()
            else:
                print(f"❌ Full reindexing failed: {result.stderr[:200]}")

        except subprocess.TimeoutExpired:
            print("⏰ Full reindexing timed out")
        except Exception as e:
            print(f"❌ Error during full reindexing: {e}")

# Global instance
updater = None

def init_updater(docs_dir):
    """Initialize the knowledge base updater"""
    global updater
    updater = KnowledgeBaseUpdater(docs_dir)
    return updater

def check_and_update():
    """Check for changes and update if needed"""
    global updater
    if updater:
        changes = updater.check_for_changes()
        if changes:
            updater.trigger_reindexing(changes)
        return changes
    return None
