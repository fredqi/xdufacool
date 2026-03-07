# dupcheck.py ---
#
# Filename: dupcheck.py
# Author: Fred Qi
# Created: 2020-09-01 13:53:31(+0800)
#
# Last-Updated: 2026-01-24 [by GitHub Copilot]
#     Update #: 300
#

# Commentary:
#
# Duplicate file detection and cleaning module for xdufacool.
#
# Combines features from find_duplicates.py and the original dupcheck.py:
# - Checksum caching with mtime/size validation
# - Memory-mapped file reading for efficiency
# - Partial hashing for fast pre-filtering
# - Progress bar support
# - Base directory filtering for selective cleanup
#

# Change Log:
#
# 2026-01-24: Merged find_duplicates.py features (caching, CLI subcommands)
#

import os
import sys
import mmap
import hashlib
import argparse
import yaml
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

CACHE_FILENAME = ".dup_cache.yaml"


# --- Hashing Functions ---

def calculate_checksum(file_path, n_blocks=None, block_size=64 * 1024):
    """
    Calculate SHA256 checksum of a file using memory mapping.

    Args:
        file_path: Path to the file.
        n_blocks: Number of blocks to read. None means read entire file.
        block_size: Size of each block in bytes (default 64KB).

    Returns:
        Hexdigest string or None on error.
    """
    try:
        with open(file_path, 'rb') as f:
            # Handle empty files
            file_size = os.fstat(f.fileno()).st_size
            if file_size == 0:
                return hashlib.sha256(b'').hexdigest()

            with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                sha256_hash = hashlib.sha256()

                if n_blocks is None or n_blocks <= 0:
                    # Read entire file
                    total_blocks = (file_size + block_size - 1) // block_size
                else:
                    total_blocks = min(n_blocks, (file_size + block_size - 1) // block_size)

                for _ in range(total_blocks):
                    data = mm.read(block_size)
                    if not data:
                        break
                    sha256_hash.update(data)

                return sha256_hash.hexdigest()
    except (OSError, ValueError):
        return None


def calculate_partial_checksum(file_path, block_size=64 * 1024):
    """Calculate a partial checksum (first block only) for quick comparison."""
    return calculate_checksum(file_path, n_blocks=1, block_size=block_size)


def calculate_full_checksum(file_path, block_size=64 * 1024):
    """Calculate full file checksum."""
    return calculate_checksum(file_path, n_blocks=None, block_size=block_size)


# Aliases for backward compatibility
def fast_hash_file(filename, n_blocks=1, block_size=1024 * 64) -> str:
    """Legacy function name for backward compatibility."""
    return calculate_checksum(filename, n_blocks=n_blocks, block_size=block_size)


# --- Cache Management ---

def load_cache(cache_path):
    """Load checksum cache from YAML file."""
    if cache_path.exists():
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            pass
    return {}


def save_cache(cache_path, cache):
    """Save checksum cache to YAML file."""
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            yaml.dump(cache, f, default_flow_style=False, allow_unicode=True)
    except OSError as e:
        print(f"Warning: Could not save cache to {cache_path}: {e}", file=sys.stderr)


def get_cached_checksum(file_path, base_path, cache, partial=False):
    """
    Get checksum from cache or calculate it.

    Args:
        file_path: Path to the file.
        base_path: Base directory for relative path calculation.
        cache: Cache dictionary.
        partial: If True, use partial checksum; otherwise full.

    Returns:
        Tuple of (checksum, was_cached).
    """
    try:
        rel_path = str(file_path.relative_to(base_path))
        stat = file_path.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except (ValueError, OSError):
        return None, False

    cache_key = 'checksum_partial' if partial else 'checksum'

    # Check cache validity
    cached_entry = cache.get(rel_path)
    if cached_entry:
        if cached_entry.get('mtime') == mtime and cached_entry.get('size') == size:
            cached_checksum = cached_entry.get(cache_key)
            if cached_checksum:
                return cached_checksum, True

    # Calculate checksum
    if partial:
        checksum = calculate_partial_checksum(file_path)
    else:
        checksum = calculate_full_checksum(file_path)

    if checksum:
        if rel_path not in cache:
            cache[rel_path] = {}
        cache[rel_path].update({
            'mtime': mtime,
            'size': size,
            cache_key: checksum
        })

    return checksum, False


# --- Path Utilities ---

def is_child_path(filepath, parent):
    """Check if filepath is under parent directory."""
    try:
        p, thefile = Path(parent).resolve(), Path(filepath).resolve()
        return p in thefile.parents and thefile.is_file()
    except (OSError, ValueError):
        return False


def get_file_size(filename):
    """Get file size as string (legacy compatibility)."""
    return str(os.stat(filename).st_size)


# --- Legacy Functions for Backward Compatibility ---

def load_list(filename):
    """Load a file list generated by the find command for duplication check."""
    with open(filename, 'r') as infile:
        data = [ln.strip() for ln in infile.readlines()]
        files = filter(lambda x: os.path.isfile(x), data)
    return list(files)


def load_duplications(filename):
    """To load a YAML file containing a dictionary of duplicated files."""
    try:
        from yaml import CLoader as Loader
    except ImportError:
        from yaml import Loader
    with open(filename, 'r') as stream:
        duplications = yaml.load(stream, Loader=Loader)
    return duplications


def filter_dupdict(hashdict, base_dir=None):
    """Filter dictionary to only include duplicates."""
    dict_filtered = dict(filter(lambda x: len(x[1]) > 1, hashdict.items()))
    if base_dir is not None and Path(base_dir).exists():
        keys_to_ignore = []
        for key, files in dict_filtered.items():
            dup_files = [item['filename'] for item in files]
            to_keep = any(map(lambda x: is_child_path(x, base_dir), dup_files))
            if not to_keep:
                keys_to_ignore.append(key)
        for key in keys_to_ignore:
            del dict_filtered[key]
    return dict_filtered


def dupdict_to_list(dup_files):
    """Convert duplicate dict to flat list."""
    filelist = []
    for value in dup_files.values():
        filelist.extend(value)
    return filelist


def simplify_dupdict(dup_files):
    """Simplify duplicate dict to just filenames."""
    dup_simplified = {}
    for key, files in dup_files.items():
        dup_simplified[key] = [item['filename'] for item in files]
    return dup_simplified


def dupdict_to_yaml(yamlfile, dup_simplified):
    """Write simplified duplicate dict to YAML file."""
    try:
        from yaml import CDumper as Dumper
    except ImportError:
        from yaml import Dumper
    with open(yamlfile, 'w') as output:
        yaml.dump(dup_simplified, output, Dumper=Dumper, allow_unicode=True)


# --- Core Duplicate Detection ---

def scan_files(base_path, show_progress=True):
    """
    Scan directory and group files by size.

    Returns:
        Tuple of (files_by_size dict, seen_files set).
    """
    files_by_size = defaultdict(list)
    seen_files = set()

    # Count files first for progress bar
    if show_progress:
        file_count = sum(1 for _, _, files in os.walk(base_path) for _ in files)
        pbar = tqdm(total=file_count, desc="Scanning files", unit=" files")

    for root, _, files in os.walk(base_path):
        for name in files:
            if name == CACHE_FILENAME:
                continue

            file_path = Path(root) / name

            if file_path.is_symlink():
                continue

            try:
                rel_path = str(file_path.relative_to(base_path))
                seen_files.add(rel_path)
                size = file_path.stat().st_size
                files_by_size[size].append(file_path)
            except (OSError, ValueError):
                pass

            if show_progress:
                pbar.update(1)

    if show_progress:
        pbar.close()

    return files_by_size, seen_files


def find_duplicates(base_folder, show_progress=True, use_cache=True):
    """
    Find duplicate files in a directory.

    Uses a three-stage approach:
    1. Group by file size (instant)
    2. Group by partial checksum (fast)
    3. Group by full checksum (thorough)

    Args:
        base_folder: Directory to scan.
        show_progress: Show progress bars.
        use_cache: Use checksum cache.

    Returns:
        List of (checksum, relative_path) tuples, sorted by path.
    """
    base_path = Path(base_folder).resolve()
    if not base_path.is_dir():
        print(f"Error: {base_folder} is not a valid directory.", file=sys.stderr)
        return []

    cache_file = base_path / CACHE_FILENAME
    cache = load_cache(cache_file) if use_cache else {}

    # Stage 1: Group by size
    files_by_size, seen_files = scan_files(base_path, show_progress)

    # Filter to only files with matching sizes
    potential_duplicates = {s: fps for s, fps in files_by_size.items() if len(fps) > 1}

    if not potential_duplicates:
        return []

    # Flatten for progress calculation
    files_to_check = [fp for fps in potential_duplicates.values() for fp in fps]

    # Stage 2: Group by partial checksum
    if show_progress:
        pbar = tqdm(total=len(files_to_check), desc="Partial checksums", unit=" files")

    files_by_partial = defaultdict(list)
    for file_path in files_to_check:
        checksum, _ = get_cached_checksum(file_path, base_path, cache, partial=True)
        if checksum:
            files_by_partial[checksum].append(file_path)
        if show_progress:
            pbar.update(1)

    if show_progress:
        pbar.close()

    # Filter to files with matching partial checksums
    partial_matches = {h: fps for h, fps in files_by_partial.items() if len(fps) > 1}
    files_to_verify = [fp for fps in partial_matches.values() for fp in fps]

    if not files_to_verify:
        if use_cache:
            cache = {k: v for k, v in cache.items() if k in seen_files}
            save_cache(cache_file, cache)
        return []

    # Stage 3: Group by full checksum
    if show_progress:
        total_size = sum(fp.stat().st_size for fp in files_to_verify if fp.exists())
        pbar = tqdm(total=total_size, desc="Full checksums", unit="B", unit_scale=True)

    files_by_hash = defaultdict(list)
    for file_path in files_to_verify:
        file_size = file_path.stat().st_size if file_path.exists() else 0
        checksum, was_cached = get_cached_checksum(file_path, base_path, cache, partial=False)
        if checksum:
            files_by_hash[checksum].append(file_path)
        if show_progress:
            pbar.update(file_size)

    if show_progress:
        pbar.close()

    # Prune and save cache
    if use_cache:
        cache = {k: v for k, v in cache.items() if k in seen_files}
        save_cache(cache_file, cache)

    # Filter to actual duplicates
    duplicates_map = {h: fps for h, fps in files_by_hash.items() if len(fps) > 1}

    # Build sorted output
    sorted_groups = []
    for checksum, file_paths in duplicates_map.items():
        rel_paths = []
        for file_path in file_paths:
            try:
                rel_paths.append(str(file_path.relative_to(base_path)))
            except ValueError:
                continue
        if len(rel_paths) > 1:
            rel_paths.sort()
            sorted_groups.append((checksum, rel_paths))

    sorted_groups.sort(key=lambda x: x[1][0])

    # Flatten
    duplicate_entries = []
    for checksum, paths in sorted_groups:
        for path in paths:
            duplicate_entries.append((checksum, path))

    return duplicate_entries


# --- Report Generation ---

def generate_report(duplicates, base_folder, output_file):
    """Generate a YAML report of duplicates."""
    duplicates_dict = defaultdict(list)
    for checksum, path in duplicates:
        duplicates_dict[checksum].append({
            'path': path,
            'delete': False
        })

    output_data = {
        'base_dir': str(Path(base_folder).resolve()),
        'duplicates': dict(duplicates_dict)
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(output_data, f, default_flow_style=False,
                  sort_keys=False, allow_unicode=True)

    print(f"Report saved to {output_file}")


def load_report(report_file):
    """Load a YAML report file."""
    with open(report_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# --- Cleanup Functions ---

def clean_duplicates(report_file, dry_run=True):
    """
    Remove files marked for deletion in a report.

    Args:
        report_file: Path to the YAML report.
        dry_run: If True, only print what would be deleted.

    Returns:
        Number of files deleted (or would be deleted).
    """
    report = load_report(report_file)
    base_dir = Path(report['base_dir'])
    duplicates = report.get('duplicates', {})

    deleted_count = 0

    for checksum, files in duplicates.items():
        for file_info in files:
            if file_info.get('delete', False):
                file_path = base_dir / file_info['path']
                if dry_run:
                    print(f"[DRY RUN] Would delete: {file_path}")
                else:
                    try:
                        file_path.unlink(missing_ok=True)
                        print(f"Deleted: {file_path}")
                    except OSError as e:
                        print(f"Error deleting {file_path}: {e}", file=sys.stderr)
                        continue
                deleted_count += 1

    return deleted_count


def clean_by_base_dir(duplicates, base_folder, keep_dir, dry_run=True):
    """
    Remove duplicates that exist outside the keep_dir.

    Files inside keep_dir are preserved; their duplicates elsewhere are deleted.

    Args:
        duplicates: List of (checksum, rel_path) tuples.
        base_folder: Base directory of the scan.
        keep_dir: Directory whose files should be kept.
        dry_run: If True, only print what would be deleted.

    Returns:
        Number of files deleted (or would be deleted).
    """
    base_path = Path(base_folder).resolve()
    keep_path = Path(keep_dir).resolve()

    # Group by checksum
    grouped = defaultdict(list)
    for checksum, rel_path in duplicates:
        full_path = base_path / rel_path
        grouped[checksum].append(full_path)

    deleted_count = 0

    for checksum, file_paths in grouped.items():
        # Check if any file is in keep_dir
        in_keep_dir = [fp for fp in file_paths if is_child_path(fp, keep_path)]

        if not in_keep_dir:
            continue

        # Delete files outside keep_dir
        for file_path in file_paths:
            if not is_child_path(file_path, keep_path):
                if dry_run:
                    print(f"[DRY RUN] Would delete: {file_path}")
                else:
                    try:
                        file_path.unlink(missing_ok=True)
                        print(f"Deleted: {file_path}")
                    except OSError as e:
                        print(f"Error deleting {file_path}: {e}", file=sys.stderr)
                        continue
                deleted_count += 1

    return deleted_count


# Legacy function for backward compatibility
def remove_dupfile(duplications, base_dir):
    """Remove duplicated files based on base_dir (legacy function)."""
    for _, files in duplications.items():
        indicators = list(map(lambda x: is_child_path(x, base_dir), files))
        has_a_copy = any(indicators)
        if not has_a_copy:
            continue
        for to_keep, thefile in zip(indicators, files):
            if not to_keep:
                Path(thefile).unlink(missing_ok=True)
                print('DEL ', thefile)


# --- Display Functions ---

def display_duplicates(duplicates):
    """Print duplicates to stdout."""
    if not duplicates:
        print("No duplicates found.")
        return

    print(f"{'Checksum':<64}  {'File Path'}")
    print("-" * 64 + "  " + "-" * 40)

    for checksum, path in duplicates:
        print(f"{checksum}  {path}")

    print("-" * 106)
    total_files = len(duplicates)
    unique_hashes = len(set(d[0] for d in duplicates))
    redundant_files = total_files - unique_hashes

    print(f"Total files involved in duplications: {total_files}")
    print(f"Number of duplicate groups: {unique_hashes}")
    print(f"Number of redundant files: {redundant_files}")


# --- Legacy FileList Class for Backward Compatibility ---

class FileList(object):
    """Legacy class for processing file lists (backward compatibility)."""

    def __init__(self, filelist):
        self.block_size = 1024 * 1024
        self.duplications = None
        self.files = [{'filename': fn} for fn in filelist]
        self.propertyFunctions = {
            'size': get_file_size,
            'sha256-partial': lambda fn: fast_hash_file(fn, n_blocks=1),
            'sha256': lambda fn: fast_hash_file(fn, n_blocks=None),
        }

    def calc_progress(self, propertyName):
        algos = {'sha256'}
        def calc_step_size(item):
            if 'size' in item and propertyName in algos:
                item['step'] = (int(item['size']) + self.block_size - 1) // self.block_size
            else:
                item['step'] = 1
        list(map(calc_step_size, self.files))
        total_steps = sum([x['step'] for x in self.files])
        unit = ' M' if propertyName in algos else ' files'
        return tqdm(total=total_steps, unit=unit)

    def filter_files(self, base_dir):
        keys_to_ignore = []
        for key, values in self.files.items():
            dup_files = [item['filename'] for item in values]
            to_keep = any(map(lambda x: is_child_path(x, base_dir), dup_files))
            if not to_keep:
                keys_to_ignore.append(key)
        for key in keys_to_ignore:
            del self.files[key]

    def collect_property(self, propertyName):
        thefunc = self.propertyFunctions[propertyName]
        pbar = self.calc_progress(propertyName)
        for thefile in self.files:
            thefile[propertyName] = thefunc(thefile['filename'])
            pbar.update(thefile['step'])

    def find_duplication(self, propertyName, base_dir=None):
        dup_files = {}
        for thefile in self.files:
            key = thefile[propertyName]
            if key in dup_files:
                dup_files[key].append(thefile)
            else:
                dup_files[key] = [thefile]
        self.duplications = filter_dupdict(dup_files, base_dir)
        self.files = dupdict_to_list(self.duplications)


# --- CLI ---

def cmd_scan(args):
    """Scan subcommand handler."""
    duplicates = find_duplicates(
        args.folder,
        show_progress=not args.quiet,
        use_cache=not args.no_cache
    )
    if not args.quiet:
        display_duplicates(duplicates)
    if args.output:
        generate_report(duplicates, args.folder, args.output)


def cmd_clean(args):
    """Clean subcommand handler."""
    if args.report:
        count = clean_duplicates(args.report, dry_run=args.dry_run)
    else:
        print("Error: --report is required.")
        return

    action = "Would delete" if args.dry_run else "Deleted"
    print(f"\n{action} {count} files.")
    if args.dry_run:
        print("Use --execute to actually delete files.")


def cmd_gui(args):
    try:
        from xdufacool.dupcheck_qt import main as gui_main
        gui_main()
    except ImportError:
        print("Error: GUI requires PySide6. Install it with: pip install PySide6")


def main():
    parser = argparse.ArgumentParser(
        prog='dupcheck',
        description='Duplicate file detection and cleaning tool for xdufacool.'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # --- Scan subcommand ---
    scan_parser = subparsers.add_parser('scan', help='Scan for duplicate files')
    scan_parser.add_argument('folder', help='Folder to scan for duplicates')
    scan_parser.add_argument('-o', '--output', help='Output YAML report file')
    scan_parser.add_argument('-q', '--quiet', action='store_true',
                             help='Suppress progress bars')
    scan_parser.add_argument('--no-cache', action='store_true',
                             help='Disable checksum caching')
    scan_parser.set_defaults(func=cmd_scan)

    # --- Clean subcommand ---
    clean_parser = subparsers.add_parser('clean', help='Remove duplicate files')
    clean_parser.add_argument('-r', '--report', required=True,
                              help='YAML report with delete flags')
    clean_parser.add_argument('--dry-run', action='store_true', default=True,
                              help='Show what would be deleted (default)')
    clean_parser.add_argument('--execute', dest='dry_run', action='store_false',
                              help='Actually delete files')
    clean_parser.set_defaults(func=cmd_clean)

    gui_parser = subparsers.add_parser('gui', help='Launch graphical editor')
    gui_parser.set_defaults(func=cmd_gui)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


# Legacy entry point for backward compatibility
def remove_dup_files():
    """Remove duplicated files based on the results of fdupes (legacy)."""
    parser = argparse.ArgumentParser(description='Remove dup files')
    parser.add_argument('--base-dir', '-d', type=str,
                        help='The base directory for reference, files should be kept')
    parser.add_argument('--backup-dir', '-b', type=str,
                        help='The backup directory where duplicated files should be removed.')
    parser.add_argument('--dup-log', '-l', type=str,
                        help='A YAML file of duplicated files for logging.')
    parser.add_argument('filelist', type=str,
                        help='List of files created by find for duplication check.')

    args = parser.parse_args()

    files = load_list(args.filelist)
    filelist = FileList(files)
    for prop in ['size', 'sha256-partial', 'sha256']:
        filelist.collect_property(prop)
        base_dir = args.base_dir if prop == 'size' else None
        filelist.find_duplication(prop, base_dir)
    dup_simplified = simplify_dupdict(filelist.duplications)
    if args.dup_log:
        dupdict_to_yaml(args.dup_log, dup_simplified)
    if args.base_dir:
        remove_dupfile(dup_simplified, args.base_dir)


if __name__ == "__main__":
    main()

#
# dupcheck.py ends here
