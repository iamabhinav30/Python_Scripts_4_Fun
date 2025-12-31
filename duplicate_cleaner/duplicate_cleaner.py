"""
D: Drive Duplicate Cleaner Agent
A safe, production-grade duplicate file finder and remover for Windows.

Author: Generated for Python_Scripts_4_Fun
Python Version: 3.11+
Platform: Windows 10/11
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import csv


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FileInfo:
    """Represents a file with metadata."""
    path: str
    size: int
    ctime: float
    mtime: float
    hash: Optional[str] = None
    folder_score: Optional[int] = None


@dataclass
class DuplicateAction:
    """Records an action taken on a duplicate file."""
    hash: str
    size: int
    kept_path: str
    removed_path: str
    reason: str
    kept_ctime: float
    kept_mtime: float
    removed_ctime: float
    removed_mtime: float
    action: str  # 'move', 'delete', 'dry-run'
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


# ============================================================================
# HASHER
# ============================================================================

class Hasher:
    """Handles file hashing with streaming and partial hash optimization."""

    CHUNK_SIZE = 65536  # 64KB chunks
    PARTIAL_HASH_SIZE = 1024 * 1024  # 1MB for partial hash

    @staticmethod
    def compute_partial_hash(filepath: str) -> Optional[str]:
        """
        Compute a fast partial hash (beginning, middle, end) for quick duplicate detection.
        Returns None if file cannot be read.
        """
        try:
            hasher = hashlib.sha256()
            file_size = os.path.getsize(filepath)

            with open(filepath, 'rb') as f:
                # Read beginning
                chunk = f.read(Hasher.CHUNK_SIZE)
                hasher.update(chunk)

                # Read middle if file is large enough
                if file_size > 2 * Hasher.CHUNK_SIZE:
                    f.seek(file_size // 2)
                    chunk = f.read(Hasher.CHUNK_SIZE)
                    hasher.update(chunk)

                # Read end if file is large enough
                if file_size > 3 * Hasher.CHUNK_SIZE:
                    f.seek(-Hasher.CHUNK_SIZE, 2)
                    chunk = f.read(Hasher.CHUNK_SIZE)
                    hasher.update(chunk)

            return hasher.hexdigest()
        except (OSError, IOError, PermissionError) as e:
            logging.debug(f"Cannot compute partial hash for {filepath}: {e}")
            return None

    @staticmethod
    def compute_full_hash(filepath: str) -> Optional[str]:
        """
        Compute full SHA-256 hash of file using streaming.
        Returns None if file cannot be read.
        """
        try:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                while chunk := f.read(Hasher.CHUNK_SIZE):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError, PermissionError) as e:
            logging.debug(f"Cannot compute full hash for {filepath}: {e}")
            return None


# ============================================================================
# DECISION ENGINE
# ============================================================================

class DecisionEngine:
    """Determines which duplicate to keep based on folder importance and other rules."""

    PROJECT_INDICATORS = {
        'package.json', 'package-lock.json', 'yarn.lock', 'pom.xml',
        'build.gradle', 'settings.gradle', 'angular.json', 'tsconfig.json',
        'pyproject.toml', 'setup.py', 'requirements.txt', 'Pipfile',
        'Cargo.toml', 'go.mod', 'composer.json', '.gitignore', '.git',
        'Makefile', 'CMakeLists.txt', '.sln', '.csproj', '.vbproj'
    }

    PROJECT_FOLDERS = {
        'src', 'source', 'lib', 'app', 'components', 'modules',
        'node_modules', '.git', '.svn', 'dist', 'build', 'target',
        'bin', 'obj', '__pycache__', 'venv', '.env'
    }

    USER_CONTENT_KEYWORDS = {
        'documents', 'photos', 'pictures', 'videos', 'music', 'downloads',
        'desktop', 'onedrive', 'dropbox', 'google drive'
    }

    IGNORE_KEYWORDS = {
        'temp', 'tmp', 'cache', 'recycle', 'trash', '$recycle.bin'
    }

    @staticmethod
    def compute_folder_score(filepath: str) -> int:
        """
        Compute importance score for the folder containing this file.
        Higher score = more important to keep.
        """
        score = 0
        path_obj = Path(filepath)
        parent = path_obj.parent
        path_lower = str(parent).lower()

        # Check for project indicators in folder
        try:
            siblings = list(parent.iterdir())
            sibling_names = {s.name.lower() for s in siblings if s.is_file()}

            # Project indicator files
            for indicator in DecisionEngine.PROJECT_INDICATORS:
                if indicator.lower() in sibling_names:
                    score += 50

            # Project folders
            sibling_dirs = {s.name.lower() for s in siblings if s.is_dir()}
            for folder in DecisionEngine.PROJECT_FOLDERS:
                if folder.lower() in sibling_dirs:
                    score += 30

            # Many sibling files with similar names (suggests organized folder)
            if len(sibling_names) > 10:
                score += 20

        except (OSError, PermissionError):
            pass

        # User content folders
        for keyword in DecisionEngine.USER_CONTENT_KEYWORDS:
            if keyword in path_lower:
                score += 40

        # Penalize temp/cache folders
        for keyword in DecisionEngine.IGNORE_KEYWORDS:
            if keyword in path_lower:
                score -= 100

        # Prefer shorter paths (closer to root)
        path_depth = len(path_obj.parts)
        score -= path_depth * 2

        return score

    @staticmethod
    def get_earliest_time(file_info: FileInfo) -> float:
        """Get the earliest timestamp (creation or modification)."""
        return min(file_info.ctime, file_info.mtime)

    @staticmethod
    def choose_file_to_keep(files: List[FileInfo]) -> FileInfo:
        """
        Choose which file to keep from a list of duplicates.
        
        Rules:
        1. Prefer higher folder score
        2. If tie, prefer oldest file
        3. If still tie, prefer shortest path
        """
        if len(files) == 1:
            return files[0]

        # Compute folder scores if not already done
        for file in files:
            if file.folder_score is None:
                file.folder_score = DecisionEngine.compute_folder_score(file.path)

        # Sort by: folder_score DESC, earliest_time ASC, path_length ASC
        sorted_files = sorted(
            files,
            key=lambda f: (
                -f.folder_score,  # Higher score first
                DecisionEngine.get_earliest_time(f),  # Older first
                len(f.path)  # Shorter path first
            )
        )

        return sorted_files[0]


# ============================================================================
# SCANNER
# ============================================================================

class Scanner:
    """Scans directories and groups files by size and hash."""

    def __init__(self, root: str, exclude_paths: List[str], exclude_globs: List[str],
                 skip_extensions: List[str], min_size: int, max_size: int):
        self.root = Path(root)
        self.exclude_paths = [Path(p).resolve() for p in exclude_paths]
        self.exclude_globs = exclude_globs
        self.skip_extensions = [ext.lower() for ext in skip_extensions]
        self.min_size = min_size
        self.max_size = max_size
        self.files_scanned = 0

    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped."""
        # Check explicit exclusions
        try:
            resolved = path.resolve()
            for excluded in self.exclude_paths:
                if resolved == excluded or excluded in resolved.parents:
                    return True
        except (OSError, RuntimeError):
            return True  # Skip paths that can't be resolved

        # Check glob patterns
        path_str = str(path).lower()
        for pattern in self.exclude_globs:
            if Path(path_str).match(pattern.lower()):
                return True

        # Check extension
        if path.suffix.lower() in self.skip_extensions:
            return True

        return False

    def scan(self) -> Dict[int, List[FileInfo]]:
        """
        Scan root directory and group files by size.
        Returns dict: {size: [FileInfo, ...]}
        """
        size_groups = defaultdict(list)
        
        logging.info(f"Starting scan of {self.root}")

        for root, dirs, files in os.walk(self.root, topdown=True, followlinks=False):
            root_path = Path(root)

            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not self.should_skip_path(root_path / d)]

            for filename in files:
                filepath = root_path / filename

                if self.should_skip_path(filepath):
                    continue

                try:
                    stat = filepath.stat()
                    size = stat.st_size

                    # Skip if outside size range
                    if size < self.min_size or size > self.max_size:
                        continue

                    file_info = FileInfo(
                        path=str(filepath),
                        size=size,
                        ctime=stat.st_ctime,
                        mtime=stat.st_mtime
                    )
                    size_groups[size].append(file_info)
                    self.files_scanned += 1

                    if self.files_scanned % 1000 == 0:
                        logging.info(f"Scanned {self.files_scanned} files...")

                except (OSError, PermissionError) as e:
                    logging.debug(f"Cannot access {filepath}: {e}")

        # Filter out unique sizes
        duplicate_candidates = {
            size: files for size, files in size_groups.items() if len(files) > 1
        }

        logging.info(f"Scan complete. {self.files_scanned} files scanned, "
                    f"{sum(len(f) for f in duplicate_candidates.values())} potential duplicates")

        return duplicate_candidates


# ============================================================================
# QUARANTINE MANAGER
# ============================================================================

class QuarantineManager:
    """Manages moving duplicates to quarantine and creating restore scripts."""

    def __init__(self, quarantine_dir: str):
        self.quarantine_dir = Path(quarantine_dir)
        self.moves: List[Tuple[str, str]] = []  # (original, quarantine_path)

    def prepare_quarantine(self):
        """Create quarantine directory if it doesn't exist."""
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Quarantine directory: {self.quarantine_dir}")

    def get_quarantine_path(self, original_path: str) -> Path:
        """Generate quarantine path preserving directory structure."""
        original = Path(original_path)
        
        # Get relative path from drive root
        try:
            # Try to get relative to root drive
            drive = Path(original.drive + "\\")
            relative = original.relative_to(drive)
        except ValueError:
            # Fallback: use full path but sanitize
            relative = Path(str(original).replace(":", "_drive"))

        return self.quarantine_dir / relative

    def move_to_quarantine(self, filepath: str) -> bool:
        """Move file to quarantine. Returns True if successful."""
        try:
            source = Path(filepath)
            dest = self.get_quarantine_path(filepath)
            
            # Create parent directories
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(source), str(dest))
            self.moves.append((filepath, str(dest)))
            logging.debug(f"Moved to quarantine: {filepath} -> {dest}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to move {filepath} to quarantine: {e}")
            return False

    def create_restore_script(self):
        """Create PowerShell script to restore all quarantined files."""
        script_path = self.quarantine_dir / "restore.ps1"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write("# Restore script for quarantined duplicates\n")
            f.write("# Generated: " + datetime.now().isoformat() + "\n\n")
            f.write("Write-Host 'Restoring quarantined files...'\n")
            f.write("$ErrorCount = 0\n\n")
            
            for original, quarantine in self.moves:
                f.write(f"# Restore: {original}\n")
                f.write(f"try {{\n")
                f.write(f"    $dest = '{original}'\n")
                f.write(f"    $destDir = Split-Path -Parent $dest\n")
                f.write(f"    if (-not (Test-Path $destDir)) {{\n")
                f.write(f"        New-Item -ItemType Directory -Path $destDir -Force | Out-Null\n")
                f.write(f"    }}\n")
                f.write(f"    Move-Item -Path '{quarantine}' -Destination $dest -Force\n")
                f.write(f"    Write-Host 'Restored: {original}'\n")
                f.write(f"}} catch {{\n")
                f.write(f"    Write-Host 'ERROR restoring {original}: $_' -ForegroundColor Red\n")
                f.write(f"    $ErrorCount++\n")
                f.write(f"}}\n\n")
            
            f.write("Write-Host \"Restore complete. Errors: $ErrorCount\"\n")

        logging.info(f"Restore script created: {script_path}")


# ============================================================================
# REPORTER
# ============================================================================

class Reporter:
    """Generates reports in CSV and JSON formats."""

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.actions: List[DuplicateAction] = []

    def add_action(self, action: DuplicateAction):
        """Add an action to the report."""
        self.actions.append(action)

    def write_reports(self):
        """Write CSV and JSON reports."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # CSV Report
        csv_path = self.log_dir / f"duplicate_report_{timestamp}.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if self.actions:
                writer = csv.DictWriter(f, fieldnames=asdict(self.actions[0]).keys())
                writer.writeheader()
                for action in self.actions:
                    writer.writerow(asdict(action))
        
        logging.info(f"CSV report: {csv_path}")

        # JSON Report
        json_path = self.log_dir / f"duplicate_report_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(a) for a in self.actions], f, indent=2)
        
        logging.info(f"JSON report: {json_path}")

        # Summary
        summary_path = self.log_dir / f"summary_{timestamp}.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Duplicate Cleaner Summary\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"=" * 60 + "\n\n")
            
            total = len(self.actions)
            errors = sum(1 for a in self.actions if a.error)
            total_size = sum(a.size for a in self.actions)
            
            f.write(f"Total duplicates processed: {total}\n")
            f.write(f"Errors encountered: {errors}\n")
            f.write(f"Space that could be freed: {self._format_size(total_size)}\n\n")
            
            by_action = defaultdict(int)
            for action in self.actions:
                by_action[action.action] += 1
            
            f.write("Actions breakdown:\n")
            for action_type, count in by_action.items():
                f.write(f"  {action_type}: {count}\n")
        
        logging.info(f"Summary: {summary_path}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class DuplicateCleaner:
    """Main orchestrator for duplicate cleaning process."""

    def __init__(self, args):
        self.args = args
        self.scanner = Scanner(
            root=args.root,
            exclude_paths=args.exclude,
            exclude_globs=args.exclude_glob,
            skip_extensions=args.skip_ext,
            min_size=args.min_size,
            max_size=args.max_size
        )
        self.reporter = Reporter(args.log_dir)
        self.quarantine_manager = None
        if args.mode == 'quarantine':
            quarantine_dir = Path(args.root) / "_DUPLICATE_QUARANTINE"
            self.quarantine_manager = QuarantineManager(str(quarantine_dir))

    def find_duplicates_by_hash(self, size_groups: Dict[int, List[FileInfo]], 
                                workers: int) -> Dict[str, List[FileInfo]]:
        """
        Hash files and group by hash to find true duplicates.
        Uses partial hash first, then full hash for confirmation.
        """
        hash_groups = defaultdict(list)
        total_files = sum(len(files) for files in size_groups.values())
        
        logging.info(f"Computing hashes for {total_files} files using {workers} workers...")
        
        processed = 0
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all files for partial hashing
            future_to_file = {}
            for size, files in size_groups.items():
                for file_info in files:
                    future = executor.submit(Hasher.compute_partial_hash, file_info.path)
                    future_to_file[future] = (file_info, 'partial')
            
            # Collect partial hashes
            partial_groups = defaultdict(list)
            for future in as_completed(future_to_file):
                file_info, _ = future_to_file[future]
                partial_hash = future.result()
                if partial_hash:
                    partial_groups[partial_hash].append(file_info)
                processed += 1
                if processed % 100 == 0:
                    logging.info(f"Hashed {processed}/{total_files} files...")
            
            # Now compute full hashes only for files with matching partial hashes
            candidates = [files for files in partial_groups.values() if len(files) > 1]
            candidate_files = [f for group in candidates for f in group]
            
            if candidate_files:
                logging.info(f"Computing full hashes for {len(candidate_files)} candidate duplicates...")
                
                future_to_file = {}
                for file_info in candidate_files:
                    future = executor.submit(Hasher.compute_full_hash, file_info.path)
                    future_to_file[future] = (file_info, 'full')
                
                for future in as_completed(future_to_file):
                    file_info, _ = future_to_file[future]
                    full_hash = future.result()
                    if full_hash:
                        file_info.hash = full_hash
                        hash_groups[full_hash].append(file_info)
        
        # Filter to only true duplicates
        duplicates = {h: files for h, files in hash_groups.items() if len(files) > 1}
        
        total_duplicates = sum(len(files) - 1 for files in duplicates.values())
        logging.info(f"Found {total_duplicates} duplicate files in {len(duplicates)} groups")
        
        return duplicates

    def process_duplicates(self, hash_groups: Dict[str, List[FileInfo]]):
        """Process each group of duplicates and take action."""
        total_groups = len(hash_groups)
        processed = 0
        
        for file_hash, files in hash_groups.items():
            processed += 1
            
            # Choose which file to keep
            keeper = DecisionEngine.choose_file_to_keep(files)
            
            # Process files to remove
            for file_info in files:
                if file_info.path == keeper.path:
                    continue
                
                reason = self._build_reason(keeper, file_info)
                action_type = 'dry-run'
                error = None
                
                if self.args.apply:
                    if self.args.mode == 'delete':
                        if self.args.confirm:
                            try:
                                os.remove(file_info.path)
                                action_type = 'delete'
                            except Exception as e:
                                error = str(e)
                                logging.error(f"Failed to delete {file_info.path}: {e}")
                        else:
                            error = "Confirm flag not set"
                            logging.warning("Delete mode requires --confirm flag")
                    
                    elif self.args.mode == 'quarantine':
                        if self.quarantine_manager.move_to_quarantine(file_info.path):
                            action_type = 'move'
                        else:
                            error = "Move failed"
                    
                    elif self.args.mode == 'report':
                        action_type = 'report-only'
                else:
                    action_type = 'dry-run'
                
                action = DuplicateAction(
                    hash=file_hash,
                    size=file_info.size,
                    kept_path=keeper.path,
                    removed_path=file_info.path,
                    reason=reason,
                    kept_ctime=keeper.ctime,
                    kept_mtime=keeper.mtime,
                    removed_ctime=file_info.ctime,
                    removed_mtime=file_info.mtime,
                    action=action_type,
                    error=error
                )
                self.reporter.add_action(action)
            
            if processed % 10 == 0:
                logging.info(f"Processed {processed}/{total_groups} duplicate groups...")

    def _build_reason(self, keeper: FileInfo, removed: FileInfo) -> str:
        """Build human-readable reason for keeping one file over another."""
        reasons = []
        
        if keeper.folder_score > removed.folder_score:
            reasons.append(f"better folder score ({keeper.folder_score} vs {removed.folder_score})")
        
        keeper_earliest = DecisionEngine.get_earliest_time(keeper)
        removed_earliest = DecisionEngine.get_earliest_time(removed)
        if keeper_earliest < removed_earliest:
            reasons.append("older file")
        
        if len(keeper.path) < len(removed.path):
            reasons.append("shorter path")
        
        return "; ".join(reasons) if reasons else "default choice"

    def run(self):
        """Main execution flow."""
        logging.info("=" * 60)
        logging.info("Duplicate Cleaner Agent")
        logging.info("=" * 60)
        logging.info(f"Root: {self.args.root}")
        logging.info(f"Mode: {self.args.mode}")
        logging.info(f"Dry run: {not self.args.apply}")
        logging.info("=" * 60)

        # Phase 1: Scan and group by size
        size_groups = self.scanner.scan()
        
        if not size_groups:
            logging.info("No potential duplicates found.")
            return

        # Phase 2: Hash and find true duplicates
        hash_groups = self.find_duplicates_by_hash(size_groups, self.args.workers)
        
        if not hash_groups:
            logging.info("No true duplicates found.")
            return

        # Prepare quarantine if needed
        if self.args.mode == 'quarantine' and self.args.apply:
            self.quarantine_manager.prepare_quarantine()

        # Phase 3: Process duplicates
        self.process_duplicates(hash_groups)

        # Generate reports
        self.reporter.write_reports()

        # Create restore script if quarantine was used
        if self.args.mode == 'quarantine' and self.args.apply and self.quarantine_manager.moves:
            self.quarantine_manager.create_restore_script()

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print final summary to console."""
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        total = len(self.reporter.actions)
        errors = sum(1 for a in self.reporter.actions if a.error)
        total_size = sum(a.size for a in self.reporter.actions)
        
        print(f"Total duplicates found: {total}")
        print(f"Errors: {errors}")
        print(f"Potential space savings: {Reporter._format_size(total_size)}")
        
        if not self.args.apply:
            print("\n⚠️  DRY RUN MODE - No files were modified")
            print("   Use --apply to actually perform actions")
        elif self.args.mode == 'delete' and not self.args.confirm:
            print("\n⚠️  DELETE MODE requires --confirm flag")
        
        print(f"\nReports saved to: {self.reporter.log_dir}")
        print("=" * 60)


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Safe duplicate file cleaner for Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default) - just scan and report
  python duplicate_cleaner.py --root "D:\\"
  
  # Quarantine duplicates (safest)
  python duplicate_cleaner.py --root "D:\\" --apply --mode quarantine
  
  # Delete duplicates (requires confirm)
  python duplicate_cleaner.py --root "D:\\" --apply --mode delete --confirm
  
  # Exclude specific folders
  python duplicate_cleaner.py --root "D:\\" --exclude "D:\\Games" "D:\\VMs"
  
  # Skip certain file types
  python duplicate_cleaner.py --root "D:\\" --skip-ext ".iso" ".vhdx" ".vmdk"
        """
    )
    
    parser.add_argument('--root', required=True,
                       help='Root directory to scan (e.g., "D:\\")')
    
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Dry run mode (default: True)')
    
    parser.add_argument('--apply', action='store_true',
                       help='Actually perform actions (disables dry-run)')
    
    parser.add_argument('--mode', choices=['report', 'quarantine', 'delete'],
                       default='quarantine',
                       help='Action mode (default: quarantine)')
    
    parser.add_argument('--exclude', nargs='+', default=[],
                       help='Directories to exclude (absolute paths)')
    
    parser.add_argument('--exclude-glob', nargs='+', default=[],
                       help='Glob patterns to exclude (e.g., "*.tmp")')
    
    parser.add_argument('--skip-ext', nargs='+', default=[],
                       help='File extensions to skip (e.g., ".iso" ".log")')
    
    parser.add_argument('--min-size', type=int, default=0,
                       help='Minimum file size in bytes (default: 0)')
    
    parser.add_argument('--max-size', type=int, default=10**12,
                       help='Maximum file size in bytes (default: 1TB)')
    
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of worker threads for hashing (default: 4)')
    
    parser.add_argument('--log-dir', default=None,
                       help='Log directory (default: <root>/_DUPLICATE_LOGS)')
    
    parser.add_argument('--confirm', action='store_true',
                       help='Required safety flag for delete mode')
    
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set default log directory if not specified
    if not args.log_dir:
        args.log_dir = str(Path(args.root) / "_DUPLICATE_LOGS")
    
    # Add system folders to exclusions
    system_excludes = [
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData"
    ]
    args.exclude.extend([p for p in system_excludes if Path(p).exists()])
    
    return args


def setup_logging(verbose: bool, log_dir: str):
    """Setup logging configuration."""
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"duplicate_cleaner_{timestamp}.log"
    
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    setup_logging(args.verbose, args.log_dir)
    
    # Validate root path
    if not Path(args.root).exists():
        logging.error(f"Root path does not exist: {args.root}")
        sys.exit(1)
    
    # Safety check for delete mode
    if args.mode == 'delete' and args.apply and not args.confirm:
        logging.error("DELETE mode with --apply requires --confirm flag for safety")
        sys.exit(1)
    
    try:
        cleaner = DuplicateCleaner(args)
        cleaner.run()
    except KeyboardInterrupt:
        logging.warning("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
