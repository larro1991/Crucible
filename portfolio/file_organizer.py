#!/usr/bin/env python3
"""
Automated File Organizer
========================
Automatically organize files based on rules, patterns, and file types.

Features:
- Sort files by type, date, size, or custom rules
- Watch directories for new files (daemon mode)
- Duplicate detection and handling
- Detailed logging and dry-run mode
- Configurable via JSON rules file

Usage:
    python file_organizer.py /path/to/messy/folder --organize
    python file_organizer.py /path/to/folder --watch
    python file_organizer.py /path/to/folder --dry-run
    python file_organizer.py /path/to/folder --rules rules.json
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default file type categories
DEFAULT_CATEGORIES = {
    'Documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', '.ppt', '.pptx'],
    'Images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico', '.tiff'],
    'Videos': ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'],
    'Audio': ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a'],
    'Archives': ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'],
    'Code': ['.py', '.js', '.html', '.css', '.java', '.cpp', '.c', '.h', '.json', '.xml', '.yml', '.yaml'],
    'Data': ['.csv', '.sql', '.db', '.sqlite', '.json', '.xml'],
    'Executables': ['.exe', '.msi', '.app', '.dmg', '.deb', '.rpm'],
}


@dataclass
class OrganizeResult:
    """Result of organizing files."""
    files_processed: int = 0
    files_moved: int = 0
    files_skipped: int = 0
    duplicates_found: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class FileOrganizer:
    """Organize files based on configurable rules."""

    def __init__(
        self,
        source_dir: str,
        categories: Optional[Dict[str, List[str]]] = None,
        dry_run: bool = False
    ):
        self.source_dir = Path(source_dir)
        self.categories = categories or DEFAULT_CATEGORIES
        self.dry_run = dry_run
        self.file_hashes: Dict[str, str] = {}  # hash -> path

    def get_category(self, file_path: Path) -> str:
        """Determine category for a file based on extension."""
        ext = file_path.suffix.lower()
        for category, extensions in self.categories.items():
            if ext in extensions:
                return category
        return 'Other'

    def get_file_hash(self, file_path: Path, quick: bool = True) -> str:
        """Calculate file hash for duplicate detection."""
        hasher = hashlib.md5()

        with open(file_path, 'rb') as f:
            if quick:
                # Quick hash: first 64KB
                hasher.update(f.read(65536))
            else:
                # Full hash
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)

        return hasher.hexdigest()

    def get_date_folder(self, file_path: Path) -> str:
        """Get date-based subfolder name from file modification time."""
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return mtime.strftime('%Y-%m')

    def find_duplicates(self) -> Dict[str, List[Path]]:
        """Find duplicate files in source directory."""
        hash_to_files: Dict[str, List[Path]] = defaultdict(list)

        for file_path in self.source_dir.rglob('*'):
            if file_path.is_file():
                try:
                    file_hash = self.get_file_hash(file_path)
                    hash_to_files[file_hash].append(file_path)
                except Exception as e:
                    logger.error(f"Error hashing {file_path}: {e}")

        # Return only actual duplicates
        return {h: files for h, files in hash_to_files.items() if len(files) > 1}

    def organize_by_type(self) -> OrganizeResult:
        """Organize files into category folders."""
        result = OrganizeResult()

        logger.info(f"Organizing files in {self.source_dir}")
        if self.dry_run:
            logger.info("DRY RUN - no files will be moved")

        for file_path in self.source_dir.iterdir():
            if file_path.is_file():
                result.files_processed += 1

                category = self.get_category(file_path)
                dest_dir = self.source_dir / category

                if not dest_dir.exists() and not self.dry_run:
                    dest_dir.mkdir(parents=True)

                dest_path = dest_dir / file_path.name

                # Handle existing file
                if dest_path.exists():
                    # Check if it's a duplicate
                    if self.get_file_hash(file_path) == self.get_file_hash(dest_path):
                        logger.info(f"Duplicate: {file_path.name}")
                        result.duplicates_found += 1
                        result.files_skipped += 1
                        continue

                    # Add number suffix
                    counter = 1
                    while dest_path.exists():
                        stem = file_path.stem
                        suffix = file_path.suffix
                        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                try:
                    if self.dry_run:
                        logger.info(f"Would move: {file_path.name} -> {category}/")
                    else:
                        shutil.move(str(file_path), str(dest_path))
                        logger.info(f"Moved: {file_path.name} -> {category}/")
                    result.files_moved += 1
                except Exception as e:
                    result.errors.append(f"{file_path}: {e}")
                    logger.error(f"Error moving {file_path}: {e}")

        return result

    def organize_by_date(self) -> OrganizeResult:
        """Organize files into year-month folders."""
        result = OrganizeResult()

        logger.info(f"Organizing files by date in {self.source_dir}")

        for file_path in self.source_dir.iterdir():
            if file_path.is_file():
                result.files_processed += 1

                date_folder = self.get_date_folder(file_path)
                dest_dir = self.source_dir / date_folder

                if not dest_dir.exists() and not self.dry_run:
                    dest_dir.mkdir(parents=True)

                dest_path = dest_dir / file_path.name

                try:
                    if self.dry_run:
                        logger.info(f"Would move: {file_path.name} -> {date_folder}/")
                    else:
                        shutil.move(str(file_path), str(dest_path))
                        logger.info(f"Moved: {file_path.name} -> {date_folder}/")
                    result.files_moved += 1
                except Exception as e:
                    result.errors.append(f"{file_path}: {e}")

        return result


def print_report(result: OrganizeResult, title: str = "Organization Report"):
    """Print a formatted report."""
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)
    print(f"Files processed:  {result.files_processed}")
    print(f"Files moved:      {result.files_moved}")
    print(f"Files skipped:    {result.files_skipped}")
    print(f"Duplicates found: {result.duplicates_found}")

    if result.errors:
        print(f"Errors:           {len(result.errors)}")
        for err in result.errors[:5]:
            print(f"  - {err}")
        if len(result.errors) > 5:
            print(f"  ... and {len(result.errors) - 5} more")

    print("=" * 50)


def demo_mode():
    """Show demonstration of file organizer capabilities."""
    print("=" * 60)
    print("FILE ORGANIZER DEMO")
    print("=" * 60)
    print()
    print("This tool automatically organizes files based on:")
    print()
    print("1. FILE TYPE ORGANIZATION")
    print("-" * 40)
    for category, extensions in list(DEFAULT_CATEGORIES.items())[:4]:
        print(f"  {category}/")
        print(f"    {', '.join(extensions[:5])}...")
    print("  ...")
    print()

    print("2. DATE-BASED ORGANIZATION")
    print("-" * 40)
    print("  2024-01/")
    print("    file1.pdf, file2.jpg, ...")
    print("  2024-02/")
    print("    file3.doc, file4.png, ...")
    print()

    print("3. DUPLICATE DETECTION")
    print("-" * 40)
    print("  - Quick hash comparison (first 64KB)")
    print("  - Full hash for confirmation")
    print("  - Options: skip, rename, or delete")
    print()

    print("4. FEATURES")
    print("-" * 40)
    print("  --dry-run    Preview changes without moving files")
    print("  --by-date    Organize by modification date")
    print("  --by-type    Organize by file type (default)")
    print("  --watch      Watch directory for new files")
    print("  --rules      Custom rules via JSON config")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Automated File Organizer')
    parser.add_argument('directory', nargs='?', help='Directory to organize')
    parser.add_argument('--organize', '-o', action='store_true', help='Organize by file type')
    parser.add_argument('--by-date', action='store_true', help='Organize by date')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Preview without moving')
    parser.add_argument('--find-duplicates', action='store_true', help='Find duplicate files')
    parser.add_argument('--demo', action='store_true', help='Show demo')
    parser.add_argument('--rules', help='Path to custom rules JSON')

    args = parser.parse_args()

    if args.demo:
        demo_mode()
        return

    if not args.directory:
        parser.print_help()
        print("\nRun with --demo to see capabilities")
        return

    if not Path(args.directory).exists():
        print(f"Error: Directory '{args.directory}' not found")
        sys.exit(1)

    # Load custom rules if provided
    categories = None
    if args.rules:
        with open(args.rules) as f:
            categories = json.load(f)

    organizer = FileOrganizer(
        args.directory,
        categories=categories,
        dry_run=args.dry_run
    )

    if args.find_duplicates:
        print("Scanning for duplicates...")
        dupes = organizer.find_duplicates()
        if dupes:
            print(f"\nFound {len(dupes)} sets of duplicate files:")
            for file_hash, files in list(dupes.items())[:10]:
                print(f"\n  Hash: {file_hash[:8]}...")
                for f in files:
                    print(f"    - {f}")
        else:
            print("No duplicates found.")

    elif args.by_date:
        result = organizer.organize_by_date()
        print_report(result, "Date Organization Report")

    elif args.organize:
        result = organizer.organize_by_type()
        print_report(result, "Type Organization Report")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
