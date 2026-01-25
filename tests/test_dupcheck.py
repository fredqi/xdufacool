"""
Tests for the dupcheck module.

This test suite covers:
- Checksum calculation (partial and full)
- Cache management (load, save, validation)
- Duplicate detection
- Report generation and loading
- Cleanup functions
- Path utilities
"""

import os
import tempfile
import shutil
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import io
import yaml

from xdufacool.dupcheck import (
    # Hashing functions
    calculate_checksum,
    calculate_partial_checksum,
    calculate_full_checksum,
    fast_hash_file,
    # Cache functions
    load_cache,
    save_cache,
    get_cached_checksum,
    CACHE_FILENAME,
    # Path utilities
    is_child_path,
    get_file_size,
    # Core detection
    scan_files,
    find_duplicates,
    # Report functions
    generate_report,
    load_report,
    # Cleanup functions
    clean_duplicates,
    clean_by_base_dir,
    # CLI functions
    cmd_scan,
    # Legacy functions
    load_list,
    filter_dupdict,
    dupdict_to_list,
    simplify_dupdict,
    dupdict_to_yaml,
    FileList,
)


class TestChecksumFunctions(TestCase):
    """Tests for checksum calculation functions."""

    def setUp(self):
        """Create a temporary directory with test files."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create a test file with known content
        self.test_file = Path(self.test_dir) / "test.txt"
        self.test_content = b"Hello, World! This is a test file for checksum calculation."
        with open(self.test_file, 'wb') as f:
            f.write(self.test_content)
        
        # Create an empty file
        self.empty_file = Path(self.test_dir) / "empty.txt"
        self.empty_file.touch()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_calculate_checksum_full(self):
        """Test full checksum calculation."""
        checksum = calculate_checksum(self.test_file)
        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 64)  # SHA256 produces 64 hex chars
        
        # Same file should produce same checksum
        checksum2 = calculate_checksum(self.test_file)
        self.assertEqual(checksum, checksum2)

    def test_calculate_checksum_partial(self):
        """Test partial checksum calculation."""
        partial = calculate_partial_checksum(self.test_file)
        full = calculate_full_checksum(self.test_file)
        
        self.assertIsNotNone(partial)
        self.assertIsNotNone(full)
        
        # For small files, partial and full should be the same
        self.assertEqual(partial, full)

    def test_calculate_checksum_empty_file(self):
        """Test checksum of empty file."""
        checksum = calculate_checksum(self.empty_file)
        self.assertIsNotNone(checksum)
        # SHA256 of empty string is a known value
        self.assertEqual(
            checksum,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_calculate_checksum_nonexistent_file(self):
        """Test checksum of non-existent file returns None."""
        checksum = calculate_checksum(Path(self.test_dir) / "nonexistent.txt")
        self.assertIsNone(checksum)

    def test_fast_hash_file_compatibility(self):
        """Test that fast_hash_file (legacy) works correctly."""
        checksum = fast_hash_file(str(self.test_file), n_blocks=None)
        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 64)


class TestCacheManagement(TestCase):
    """Tests for cache loading and saving."""

    def setUp(self):
        """Create a temporary directory for cache tests."""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / CACHE_FILENAME

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_load_cache_nonexistent(self):
        """Test loading cache from non-existent file."""
        cache = load_cache(self.cache_path)
        self.assertEqual(cache, {})

    def test_save_and_load_cache(self):
        """Test saving and loading cache."""
        test_cache = {
            'file1.txt': {
                'mtime': 1234567890.0,
                'size': 1024,
                'checksum': 'abc123'
            },
            'file2.txt': {
                'mtime': 1234567891.0,
                'size': 2048,
                'checksum': 'def456'
            }
        }
        
        save_cache(self.cache_path, test_cache)
        self.assertTrue(self.cache_path.exists())
        
        loaded = load_cache(self.cache_path)
        self.assertEqual(loaded, test_cache)

    def test_load_cache_invalid_yaml(self):
        """Test loading cache from invalid YAML file."""
        with open(self.cache_path, 'w') as f:
            f.write("{ invalid yaml [")
        
        cache = load_cache(self.cache_path)
        self.assertEqual(cache, {})

    def test_get_cached_checksum_cache_hit(self):
        """Test cache hit scenario."""
        # Create a test file
        test_file = Path(self.test_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        stat = test_file.stat()
        cache = {
            'test.txt': {
                'mtime': stat.st_mtime,
                'size': stat.st_size,
                'checksum': 'cached_checksum_value'
            }
        }
        
        checksum, was_cached = get_cached_checksum(
            test_file, Path(self.test_dir), cache, partial=False
        )
        
        self.assertEqual(checksum, 'cached_checksum_value')
        self.assertTrue(was_cached)

    def test_get_cached_checksum_cache_miss(self):
        """Test cache miss scenario (file changed)."""
        # Create a test file
        test_file = Path(self.test_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Cache with wrong mtime
        cache = {
            'test.txt': {
                'mtime': 0.0,  # Wrong mtime
                'size': 12,
                'checksum': 'old_checksum'
            }
        }
        
        checksum, was_cached = get_cached_checksum(
            test_file, Path(self.test_dir), cache, partial=False
        )
        
        self.assertIsNotNone(checksum)
        self.assertFalse(was_cached)
        self.assertNotEqual(checksum, 'old_checksum')


class TestPathUtilities(TestCase):
    """Tests for path utility functions."""

    def setUp(self):
        """Create a temporary directory structure."""
        self.test_dir = tempfile.mkdtemp()
        self.subdir = Path(self.test_dir) / "subdir"
        self.subdir.mkdir()
        
        self.test_file = self.subdir / "test.txt"
        with open(self.test_file, 'w') as f:
            f.write("test")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_is_child_path_true(self):
        """Test is_child_path returns True for child files."""
        result = is_child_path(self.test_file, self.test_dir)
        self.assertTrue(result)

    def test_is_child_path_false(self):
        """Test is_child_path returns False for non-child paths."""
        result = is_child_path(self.test_file, "/some/other/path")
        self.assertFalse(result)

    def test_is_child_path_directory(self):
        """Test is_child_path returns False for directories."""
        result = is_child_path(self.subdir, self.test_dir)
        self.assertFalse(result)  # Should return False because it's a dir, not file

    def test_get_file_size(self):
        """Test get_file_size returns correct size as string."""
        size = get_file_size(str(self.test_file))
        self.assertEqual(size, "4")  # "test" is 4 bytes


class TestDuplicateDetection(TestCase):
    """Tests for duplicate detection functionality."""

    def setUp(self):
        """Create a temporary directory with duplicate files."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create duplicate files
        self.content1 = b"This is duplicate content for testing."
        self.content2 = b"This is unique content."
        
        # Create duplicates in different locations
        self.dup1 = Path(self.test_dir) / "dup1.txt"
        self.dup2 = Path(self.test_dir) / "subdir" / "dup2.txt"
        
        (Path(self.test_dir) / "subdir").mkdir()
        
        with open(self.dup1, 'wb') as f:
            f.write(self.content1)
        with open(self.dup2, 'wb') as f:
            f.write(self.content1)
        
        # Create a unique file
        self.unique = Path(self.test_dir) / "unique.txt"
        with open(self.unique, 'wb') as f:
            f.write(self.content2)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_scan_files(self):
        """Test scan_files returns correct file groupings."""
        files_by_size, seen_files = scan_files(
            Path(self.test_dir), show_progress=False
        )
        
        # Should have seen all 3 files
        self.assertEqual(len(seen_files), 3)
        
        # Duplicate files have same size
        dup_size = len(self.content1)
        self.assertIn(dup_size, files_by_size)
        self.assertEqual(len(files_by_size[dup_size]), 2)

    def test_find_duplicates(self):
        """Test find_duplicates detects duplicates correctly."""
        duplicates = find_duplicates(
            self.test_dir, show_progress=False, use_cache=False
        )
        
        # Should find 2 duplicate files
        self.assertEqual(len(duplicates), 2)
        
        # Both should have the same checksum
        checksums = [d[0] for d in duplicates]
        self.assertEqual(checksums[0], checksums[1])
        
        # Paths should include both duplicate files
        paths = [d[1] for d in duplicates]
        self.assertIn("dup1.txt", paths)
        self.assertIn("subdir/dup2.txt", paths)

    def test_find_duplicates_no_duplicates(self):
        """Test find_duplicates with no duplicates."""
        # Remove one duplicate
        self.dup2.unlink()
        
        duplicates = find_duplicates(
            self.test_dir, show_progress=False, use_cache=False
        )
        
        self.assertEqual(len(duplicates), 0)

    def test_find_duplicates_with_cache(self):
        """Test find_duplicates creates and uses cache."""
        cache_file = Path(self.test_dir) / CACHE_FILENAME
        
        # First run - should create cache
        duplicates1 = find_duplicates(
            self.test_dir, show_progress=False, use_cache=True
        )
        
        self.assertTrue(cache_file.exists())
        
        # Second run - should use cache
        duplicates2 = find_duplicates(
            self.test_dir, show_progress=False, use_cache=True
        )
        
        # Results should be the same
        self.assertEqual(len(duplicates1), len(duplicates2))


class TestReportFunctions(TestCase):
    """Tests for report generation and loading."""

    def setUp(self):
        """Create a temporary directory for report tests."""
        self.test_dir = tempfile.mkdtemp()
        self.report_file = Path(self.test_dir) / "report.yaml"

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_generate_and_load_report(self):
        """Test generating and loading a report."""
        duplicates = [
            ("checksum1", "file1.txt"),
            ("checksum1", "file2.txt"),
            ("checksum2", "file3.txt"),
            ("checksum2", "file4.txt"),
        ]
        
        generate_report(duplicates, self.test_dir, self.report_file)
        
        self.assertTrue(self.report_file.exists())
        
        report = load_report(self.report_file)
        
        self.assertIn('base_dir', report)
        self.assertIn('duplicates', report)
        self.assertEqual(len(report['duplicates']), 2)  # 2 checksum groups
        
        # Check structure
        for checksum, files in report['duplicates'].items():
            for file_info in files:
                self.assertIn('path', file_info)
                self.assertIn('delete', file_info)
                self.assertFalse(file_info['delete'])  # Default is False


class TestCleanupFunctions(TestCase):
    """Tests for cleanup functionality."""

    def setUp(self):
        """Create a temporary directory with files to clean."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create files
        self.file1 = Path(self.test_dir) / "file1.txt"
        self.file2 = Path(self.test_dir) / "file2.txt"
        
        with open(self.file1, 'w') as f:
            f.write("content1")
        with open(self.file2, 'w') as f:
            f.write("content2")
        
        self.report_file = Path(self.test_dir) / "report.yaml"

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_clean_duplicates_dry_run(self):
        """Test clean_duplicates in dry run mode."""
        # Create a report with files marked for deletion
        report = {
            'base_dir': str(self.test_dir),
            'duplicates': {
                'checksum1': [
                    {'path': 'file1.txt', 'delete': True},
                    {'path': 'file2.txt', 'delete': False},
                ]
            }
        }
        
        with open(self.report_file, 'w') as f:
            yaml.dump(report, f)
        
        count = clean_duplicates(self.report_file, dry_run=True)
        
        self.assertEqual(count, 1)
        # Files should still exist in dry run mode
        self.assertTrue(self.file1.exists())
        self.assertTrue(self.file2.exists())

    def test_clean_duplicates_execute(self):
        """Test clean_duplicates in execute mode."""
        report = {
            'base_dir': str(self.test_dir),
            'duplicates': {
                'checksum1': [
                    {'path': 'file1.txt', 'delete': True},
                    {'path': 'file2.txt', 'delete': False},
                ]
            }
        }
        
        with open(self.report_file, 'w') as f:
            yaml.dump(report, f)
        
        count = clean_duplicates(self.report_file, dry_run=False)
        
        self.assertEqual(count, 1)
        # file1 should be deleted, file2 should remain
        self.assertFalse(self.file1.exists())
        self.assertTrue(self.file2.exists())

    def test_clean_by_base_dir(self):
        """Test clean_by_base_dir functionality."""
        # Create a keep directory with a file
        keep_dir = Path(self.test_dir) / "keep"
        keep_dir.mkdir()
        
        keep_file = keep_dir / "keep_file.txt"
        with open(keep_file, 'w') as f:
            f.write("duplicate content")
        
        # Create a file outside keep_dir with same content
        outside_file = Path(self.test_dir) / "outside.txt"
        with open(outside_file, 'w') as f:
            f.write("duplicate content")
        
        # Create duplicate list
        duplicates = [
            ("same_checksum", "keep/keep_file.txt"),
            ("same_checksum", "outside.txt"),
        ]
        
        count = clean_by_base_dir(
            duplicates, self.test_dir, keep_dir, dry_run=True
        )
        
        self.assertEqual(count, 1)
        # Both files should still exist in dry run
        self.assertTrue(keep_file.exists())
        self.assertTrue(outside_file.exists())


class TestLegacyFunctions(TestCase):
    """Tests for backward compatibility functions."""

    def setUp(self):
        """Create temporary files for legacy function tests."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_filter_dupdict(self):
        """Test filter_dupdict removes non-duplicates."""
        hashdict = {
            'hash1': [{'filename': 'file1.txt'}, {'filename': 'file2.txt'}],
            'hash2': [{'filename': 'unique.txt'}],  # Not a duplicate
        }
        
        filtered = filter_dupdict(hashdict)
        
        self.assertIn('hash1', filtered)
        self.assertNotIn('hash2', filtered)

    def test_dupdict_to_list(self):
        """Test dupdict_to_list flattens the dictionary."""
        dup_files = {
            'hash1': [{'filename': 'file1.txt'}, {'filename': 'file2.txt'}],
            'hash2': [{'filename': 'file3.txt'}, {'filename': 'file4.txt'}],
        }
        
        file_list = dupdict_to_list(dup_files)
        
        self.assertEqual(len(file_list), 4)

    def test_simplify_dupdict(self):
        """Test simplify_dupdict extracts only filenames."""
        dup_files = {
            'hash1': [
                {'filename': 'file1.txt', 'size': 100},
                {'filename': 'file2.txt', 'size': 100}
            ],
        }
        
        simplified = simplify_dupdict(dup_files)
        
        self.assertEqual(simplified['hash1'], ['file1.txt', 'file2.txt'])

    def test_dupdict_to_yaml(self):
        """Test dupdict_to_yaml writes YAML file."""
        yaml_file = Path(self.test_dir) / "duplicates.yaml"
        dup_simplified = {
            'hash1': ['file1.txt', 'file2.txt'],
        }
        
        dupdict_to_yaml(yaml_file, dup_simplified)
        
        self.assertTrue(yaml_file.exists())
        
        with open(yaml_file, 'r') as f:
            loaded = yaml.safe_load(f)
        
        self.assertEqual(loaded, dup_simplified)

    def test_load_list(self):
        """Test load_list reads file list."""
        # Create a file list with existing files
        list_file = Path(self.test_dir) / "filelist.txt"
        
        test_file = Path(self.test_dir) / "test.txt"
        with open(test_file, 'w') as f:
            f.write("test")
        
        with open(list_file, 'w') as f:
            f.write(f"{test_file}\n")
            f.write("/nonexistent/file.txt\n")  # Should be filtered out
        
        files = load_list(list_file)
        
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], str(test_file))


class TestFileListClass(TestCase):
    """Tests for the legacy FileList class."""

    def setUp(self):
        """Create temporary files for FileList tests."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create test files
        self.file1 = Path(self.test_dir) / "file1.txt"
        self.file2 = Path(self.test_dir) / "file2.txt"
        
        with open(self.file1, 'w') as f:
            f.write("same content")
        with open(self.file2, 'w') as f:
            f.write("same content")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_filelist_initialization(self):
        """Test FileList initialization."""
        files = [str(self.file1), str(self.file2)]
        filelist = FileList(files)
        
        self.assertEqual(len(filelist.files), 2)
        self.assertEqual(filelist.files[0]['filename'], str(self.file1))

    def test_filelist_collect_size(self):
        """Test FileList.collect_property for size."""
        files = [str(self.file1)]
        filelist = FileList(files)
        
        filelist.collect_property('size')
        
        self.assertIn('size', filelist.files[0])
        self.assertEqual(filelist.files[0]['size'], str(len("same content")))


class TestIntegration(TestCase):
    """Integration tests for the complete workflow."""

    def setUp(self):
        """Create a complete test scenario."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create a realistic directory structure
        self.keep_dir = Path(self.test_dir) / "keep"
        self.backup_dir = Path(self.test_dir) / "backup"
        
        self.keep_dir.mkdir()
        self.backup_dir.mkdir()
        
        # Create duplicate files across directories
        content = b"This content is duplicated across folders."
        
        self.keep_file = self.keep_dir / "original.pdf"
        self.backup_file = self.backup_dir / "copy.pdf"
        
        with open(self.keep_file, 'wb') as f:
            f.write(content)
        with open(self.backup_file, 'wb') as f:
            f.write(content)
        
        # Create unique files
        self.unique_file = Path(self.test_dir) / "unique.doc"
        with open(self.unique_file, 'wb') as f:
            f.write(b"unique document content")

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_full_workflow(self):
        """Test the complete scan -> report -> clean workflow."""
        report_file = Path(self.test_dir) / "duplicates.yaml"
        
        # Step 1: Find duplicates
        duplicates = find_duplicates(
            self.test_dir, show_progress=False, use_cache=True
        )
        
        self.assertEqual(len(duplicates), 2)  # 2 duplicate files
        
        # Step 2: Generate report
        generate_report(duplicates, self.test_dir, report_file)
        
        self.assertTrue(report_file.exists())
        
        # Step 3: Load and modify report
        report = load_report(report_file)
        
        # Mark files outside keep_dir for deletion
        for checksum, files in report['duplicates'].items():
            for file_info in files:
                if not file_info['path'].startswith('keep/'):
                    file_info['delete'] = True
        
        # Save modified report
        with open(report_file, 'w') as f:
            yaml.dump(report, f)
        
        # Step 4: Clean (dry run first)
        count = clean_duplicates(report_file, dry_run=True)
        self.assertEqual(count, 1)
        self.assertTrue(self.backup_file.exists())
        
        # Step 5: Clean (execute)
        count = clean_duplicates(report_file, dry_run=False)
        self.assertEqual(count, 1)
        
        # Verify results
        self.assertTrue(self.keep_file.exists())
        self.assertFalse(self.backup_file.exists())
        self.assertTrue(self.unique_file.exists())


class TestCLI(TestCase):
    """Tests for CLI functions."""

    def setUp(self):
        """Create a temporary directory with duplicate files."""
        self.test_dir = tempfile.mkdtemp()
        
        # Create duplicate files
        content = b"duplicate content"
        self.dup1 = Path(self.test_dir) / "dup1.txt"
        self.dup2 = Path(self.test_dir) / "dup2.txt"
        
        with open(self.dup1, 'wb') as f:
            f.write(content)
        with open(self.dup2, 'wb') as f:
            f.write(content)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_cmd_scan_quiet(self):
        """Test scan command with quiet option produces no output."""
        class Args:
            folder = self.test_dir
            quiet = True
            no_cache = True
            output = None

        with patch('sys.stdout', new=io.StringIO()) as fake_stdout:
            # Also patch stderr to avoid polluting test output with progress bars if they were to appear
            with patch('sys.stderr', new=io.StringIO()): 
                cmd_scan(Args())
            output = fake_stdout.getvalue()
            self.assertEqual(output, "")

    def test_cmd_scan_verbose(self):
        """Test scan command without quiet option produces output."""
        class Args:
            folder = self.test_dir
            quiet = False
            no_cache = True
            output = None

        with patch('sys.stdout', new=io.StringIO()) as fake_stdout:
             # Patch stderr to suppress tqdm
            with patch('sys.stderr', new=io.StringIO()):
                cmd_scan(Args())
            output = fake_stdout.getvalue()
            self.assertIn("dup1.txt", output)
            self.assertIn("dup2.txt", output)
            self.assertIn("Checksum", output)


if __name__ == '__main__':
    import unittest
    unittest.main()
