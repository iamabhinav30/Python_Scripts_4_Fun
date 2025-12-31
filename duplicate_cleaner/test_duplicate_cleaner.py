"""
Unit tests for duplicate_cleaner.py

Run with: pytest test_duplicate_cleaner.py -v
"""

import pytest
import hashlib
import tempfile
import os
from pathlib import Path
from duplicate_cleaner import (
    Hasher, DecisionEngine, FileInfo, Scanner, 
    QuarantineManager, Reporter, DuplicateAction
)


# ============================================================================
# HASHER TESTS
# ============================================================================

class TestHasher:
    """Test the Hasher class for file hashing."""

    def test_compute_partial_hash_small_file(self, tmp_path):
        """Test partial hash computation for a small file."""
        # Create a small test file
        test_file = tmp_path / "small.txt"
        content = b"Hello World!"
        test_file.write_bytes(content)
        
        # Compute partial hash
        partial_hash = Hasher.compute_partial_hash(str(test_file))
        
        assert partial_hash is not None
        assert len(partial_hash) == 64  # SHA-256 produces 64 hex characters

    def test_compute_partial_hash_large_file(self, tmp_path):
        """Test partial hash computation for a large file."""
        # Create a large test file (5MB)
        test_file = tmp_path / "large.bin"
        with open(test_file, 'wb') as f:
            f.write(b'A' * (5 * 1024 * 1024))
        
        partial_hash = Hasher.compute_partial_hash(str(test_file))
        
        assert partial_hash is not None
        assert len(partial_hash) == 64

    def test_compute_full_hash(self, tmp_path):
        """Test full hash computation."""
        test_file = tmp_path / "test.txt"
        content = b"Test content for hashing"
        test_file.write_bytes(content)
        
        # Compute hash using our function
        computed_hash = Hasher.compute_full_hash(str(test_file))
        
        # Compute expected hash
        expected_hash = hashlib.sha256(content).hexdigest()
        
        assert computed_hash == expected_hash

    def test_compute_hash_nonexistent_file(self):
        """Test that hashing a nonexistent file returns None."""
        result = Hasher.compute_full_hash("/nonexistent/file.txt")
        assert result is None

    def test_identical_files_same_hash(self, tmp_path):
        """Test that identical files produce the same hash."""
        content = b"Duplicate content"
        
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        hash1 = Hasher.compute_full_hash(str(file1))
        hash2 = Hasher.compute_full_hash(str(file2))
        
        assert hash1 == hash2

    def test_different_files_different_hash(self, tmp_path):
        """Test that different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(b"Content A")
        file2.write_bytes(b"Content B")
        
        hash1 = Hasher.compute_full_hash(str(file1))
        hash2 = Hasher.compute_full_hash(str(file2))
        
        assert hash1 != hash2


# ============================================================================
# DECISION ENGINE TESTS
# ============================================================================

class TestDecisionEngine:
    """Test the DecisionEngine for keep decision logic."""

    def test_compute_folder_score_project_indicators(self, tmp_path):
        """Test that project indicators increase folder score."""
        # Create a project-like folder
        project_dir = tmp_path / "myproject"
        project_dir.mkdir()
        
        # Add project indicator files
        (project_dir / "package.json").write_text("{}")
        (project_dir / "tsconfig.json").write_text("{}")
        (project_dir / "test.txt").write_text("test")
        
        test_file = project_dir / "test.txt"
        score = DecisionEngine.compute_folder_score(str(test_file))
        
        # Should have positive score due to project indicators
        assert score > 0

    def test_compute_folder_score_temp_folder(self, tmp_path):
        """Test that temp folders get penalized."""
        temp_dir = tmp_path / "temp" / "cache"
        temp_dir.mkdir(parents=True)
        
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")
        
        score = DecisionEngine.compute_folder_score(str(test_file))
        
        # Should have negative score due to temp/cache keywords
        assert score < 0

    def test_compute_folder_score_user_content(self, tmp_path):
        """Test that user content folders get higher score."""
        docs_dir = tmp_path / "Documents" / "MyFiles"
        docs_dir.mkdir(parents=True)
        
        test_file = docs_dir / "important.docx"
        test_file.write_text("test")
        
        score = DecisionEngine.compute_folder_score(str(test_file))
        
        # Should have positive score due to Documents keyword
        assert score > 0

    def test_choose_file_to_keep_by_score(self):
        """Test that file with higher folder score is kept."""
        file1 = FileInfo(
            path="/temp/cache/file.txt",
            size=100,
            ctime=1000.0,
            mtime=1000.0,
            folder_score=-100
        )
        
        file2 = FileInfo(
            path="/Documents/file.txt",
            size=100,
            ctime=1000.0,
            mtime=1000.0,
            folder_score=50
        )
        
        keeper = DecisionEngine.choose_file_to_keep([file1, file2])
        
        assert keeper.path == file2.path

    def test_choose_file_to_keep_by_age(self):
        """Test that older file is kept when scores are equal."""
        file1 = FileInfo(
            path="/path/file1.txt",
            size=100,
            ctime=2000.0,  # Newer
            mtime=2000.0,
            folder_score=50
        )
        
        file2 = FileInfo(
            path="/path/file2.txt",
            size=100,
            ctime=1000.0,  # Older
            mtime=1000.0,
            folder_score=50
        )
        
        keeper = DecisionEngine.choose_file_to_keep([file1, file2])
        
        assert keeper.path == file2.path

    def test_choose_file_to_keep_by_path_length(self):
        """Test that shorter path is kept when score and age are equal."""
        file1 = FileInfo(
            path="/a/b/c/d/file.txt",  # Longer
            size=100,
            ctime=1000.0,
            mtime=1000.0,
            folder_score=50
        )
        
        file2 = FileInfo(
            path="/a/b/file.txt",  # Shorter
            size=100,
            ctime=1000.0,
            mtime=1000.0,
            folder_score=50
        )
        
        keeper = DecisionEngine.choose_file_to_keep([file1, file2])
        
        assert keeper.path == file2.path

    def test_get_earliest_time(self):
        """Test that earliest time is correctly identified."""
        file_info = FileInfo(
            path="/path/file.txt",
            size=100,
            ctime=1500.0,
            mtime=1000.0  # Earlier
        )
        
        earliest = DecisionEngine.get_earliest_time(file_info)
        assert earliest == 1000.0


# ============================================================================
# SCANNER TESTS
# ============================================================================

class TestScanner:
    """Test the Scanner class for file discovery and grouping."""

    def test_scan_basic(self, tmp_path):
        """Test basic scanning of a directory."""
        # Create test files
        (tmp_path / "file1.txt").write_bytes(b"A" * 100)
        (tmp_path / "file2.txt").write_bytes(b"B" * 100)
        (tmp_path / "file3.txt").write_bytes(b"C" * 200)
        
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[],
            exclude_globs=[],
            skip_extensions=[],
            min_size=0,
            max_size=10**9
        )
        
        size_groups = scanner.scan()
        
        # Should have 2 files of size 100
        assert 100 in size_groups
        assert len(size_groups[100]) == 2

    def test_scan_respects_min_size(self, tmp_path):
        """Test that scanner respects minimum size filter."""
        (tmp_path / "small.txt").write_bytes(b"A" * 10)
        (tmp_path / "large.txt").write_bytes(b"B" * 1000)
        
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[],
            exclude_globs=[],
            skip_extensions=[],
            min_size=100,  # Skip files smaller than 100 bytes
            max_size=10**9
        )
        
        size_groups = scanner.scan()
        
        # Should not include the 10-byte file
        assert 10 not in size_groups
        assert 1000 in size_groups

    def test_scan_respects_max_size(self, tmp_path):
        """Test that scanner respects maximum size filter."""
        (tmp_path / "small.txt").write_bytes(b"A" * 100)
        (tmp_path / "large.txt").write_bytes(b"B" * 10000)
        
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[],
            exclude_globs=[],
            skip_extensions=[],
            min_size=0,
            max_size=1000  # Skip files larger than 1000 bytes
        )
        
        size_groups = scanner.scan()
        
        # Should not include the 10000-byte file
        assert 10000 not in size_groups
        assert 100 in size_groups

    def test_scan_excludes_paths(self, tmp_path):
        """Test that scanner excludes specified paths."""
        # Create directory structure
        include_dir = tmp_path / "include"
        exclude_dir = tmp_path / "exclude"
        include_dir.mkdir()
        exclude_dir.mkdir()
        
        (include_dir / "file.txt").write_bytes(b"A" * 100)
        (exclude_dir / "file.txt").write_bytes(b"B" * 100)
        
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[str(exclude_dir)],
            exclude_globs=[],
            skip_extensions=[],
            min_size=0,
            max_size=10**9
        )
        
        size_groups = scanner.scan()
        
        # Should only have 1 file
        assert len(size_groups[100]) == 1

    def test_scan_skips_extensions(self, tmp_path):
        """Test that scanner skips specified extensions."""
        (tmp_path / "file.txt").write_bytes(b"A" * 100)
        (tmp_path / "file.log").write_bytes(b"B" * 100)
        
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[],
            exclude_globs=[],
            skip_extensions=['.log'],
            min_size=0,
            max_size=10**9
        )
        
        size_groups = scanner.scan()
        
        # Should only have 1 file (txt, not log)
        assert len(size_groups[100]) == 1


# ============================================================================
# QUARANTINE MANAGER TESTS
# ============================================================================

class TestQuarantineManager:
    """Test the QuarantineManager for quarantine operations."""

    def test_prepare_quarantine(self, tmp_path):
        """Test that quarantine directory is created."""
        quarantine_dir = tmp_path / "quarantine"
        manager = QuarantineManager(str(quarantine_dir))
        
        manager.prepare_quarantine()
        
        assert quarantine_dir.exists()
        assert quarantine_dir.is_dir()

    def test_get_quarantine_path(self, tmp_path):
        """Test quarantine path generation."""
        quarantine_dir = tmp_path / "quarantine"
        manager = QuarantineManager(str(quarantine_dir))
        
        original = "D:\\MyFolder\\SubFolder\\file.txt"
        quarantine_path = manager.get_quarantine_path(original)
        
        # Should preserve directory structure
        assert "MyFolder" in str(quarantine_path)
        assert "SubFolder" in str(quarantine_path)
        assert "file.txt" in str(quarantine_path)

    def test_move_to_quarantine(self, tmp_path):
        """Test moving a file to quarantine."""
        # Setup
        quarantine_dir = tmp_path / "quarantine"
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        source_file = source_dir / "test.txt"
        source_file.write_text("test content")
        
        manager = QuarantineManager(str(quarantine_dir))
        manager.prepare_quarantine()
        
        # Move to quarantine
        success = manager.move_to_quarantine(str(source_file))
        
        assert success
        assert not source_file.exists()  # Original should be gone
        assert len(manager.moves) == 1

    def test_create_restore_script(self, tmp_path):
        """Test restore script generation."""
        quarantine_dir = tmp_path / "quarantine"
        manager = QuarantineManager(str(quarantine_dir))
        manager.prepare_quarantine()
        
        # Simulate some moves
        manager.moves = [
            ("D:\\original\\file1.txt", str(quarantine_dir / "file1.txt")),
            ("D:\\original\\file2.txt", str(quarantine_dir / "file2.txt"))
        ]
        
        manager.create_restore_script()
        
        script_path = quarantine_dir / "restore.ps1"
        assert script_path.exists()
        
        # Check script contains restore commands
        script_content = script_path.read_text()
        assert "Move-Item" in script_content
        assert "file1.txt" in script_content


# ============================================================================
# REPORTER TESTS
# ============================================================================

class TestReporter:
    """Test the Reporter class for report generation."""

    def test_add_action(self, tmp_path):
        """Test adding actions to reporter."""
        reporter = Reporter(str(tmp_path))
        
        action = DuplicateAction(
            hash="abc123",
            size=1000,
            kept_path="/path/keep.txt",
            removed_path="/path/remove.txt",
            reason="test reason",
            kept_ctime=1000.0,
            kept_mtime=1000.0,
            removed_ctime=1100.0,
            removed_mtime=1100.0,
            action="dry-run"
        )
        
        reporter.add_action(action)
        
        assert len(reporter.actions) == 1
        assert reporter.actions[0].hash == "abc123"

    def test_write_reports(self, tmp_path):
        """Test that reports are written correctly."""
        reporter = Reporter(str(tmp_path))
        
        action = DuplicateAction(
            hash="abc123",
            size=1000,
            kept_path="/path/keep.txt",
            removed_path="/path/remove.txt",
            reason="test reason",
            kept_ctime=1000.0,
            kept_mtime=1000.0,
            removed_ctime=1100.0,
            removed_mtime=1100.0,
            action="dry-run"
        )
        reporter.add_action(action)
        
        reporter.write_reports()
        
        # Check that files were created
        csv_files = list(tmp_path.glob("duplicate_report_*.csv"))
        json_files = list(tmp_path.glob("duplicate_report_*.json"))
        summary_files = list(tmp_path.glob("summary_*.txt"))
        
        assert len(csv_files) == 1
        assert len(json_files) == 1
        assert len(summary_files) == 1

    def test_format_size(self):
        """Test size formatting."""
        assert "1.00 KB" in Reporter._format_size(1024)
        assert "1.00 MB" in Reporter._format_size(1024 * 1024)
        assert "1.00 GB" in Reporter._format_size(1024 * 1024 * 1024)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_duplicate_detection_workflow(self, tmp_path):
        """Test complete workflow from scan to duplicate detection."""
        # Create duplicate files
        content = b"Duplicate content here"
        
        (tmp_path / "file1.txt").write_bytes(content)
        (tmp_path / "file2.txt").write_bytes(content)
        (tmp_path / "unique.txt").write_bytes(b"Unique content")
        
        # Scan
        scanner = Scanner(
            root=str(tmp_path),
            exclude_paths=[],
            exclude_globs=[],
            skip_extensions=[],
            min_size=0,
            max_size=10**9
        )
        size_groups = scanner.scan()
        
        # Hash duplicates
        hash_groups = {}
        for size, files in size_groups.items():
            if len(files) > 1:
                for file_info in files:
                    file_hash = Hasher.compute_full_hash(file_info.path)
                    if file_hash:
                        if file_hash not in hash_groups:
                            hash_groups[file_hash] = []
                        file_info.hash = file_hash
                        hash_groups[file_hash].append(file_info)
        
        # Should have found duplicates
        duplicates = {h: f for h, f in hash_groups.items() if len(f) > 1}
        assert len(duplicates) > 0
        
        # Choose which to keep
        for file_hash, files in duplicates.items():
            keeper = DecisionEngine.choose_file_to_keep(files)
            assert keeper is not None


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_file_info():
    """Create sample FileInfo objects for testing."""
    return [
        FileInfo(
            path="/path/to/file1.txt",
            size=1000,
            ctime=1000.0,
            mtime=1000.0,
            hash="abc123"
        ),
        FileInfo(
            path="/path/to/file2.txt",
            size=1000,
            ctime=1100.0,
            mtime=1100.0,
            hash="abc123"
        )
    ]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
