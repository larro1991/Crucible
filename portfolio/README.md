# Automation Portfolio

Sample scripts demonstrating Python automation capabilities.

## Scripts

### 1. CSV Data Processor (`csv_data_processor.py`)
Automated data cleaning and transformation pipeline.

**Features:**
- Automatic column type detection (numeric, date, text)
- Data cleaning (whitespace, date normalization, null handling)
- Summary statistics and detailed reports
- Batch processing for large files

**Usage:**
```bash
python csv_data_processor.py input.csv output.csv --report report.txt
```

---

### 2. API Integration Framework (`api_integration.py`)
Connect and sync data between multiple APIs/services.

**Features:**
- Generic API client with retry logic
- Rate limiting to respect API limits
- Data transformation between different formats
- Batch processing with progress tracking

**Usage:**
```bash
python api_integration.py --demo
python api_integration.py --config config.json
```

---

### 3. File Organizer (`file_organizer.py`)
Automatically organize files based on rules, patterns, and file types.

**Features:**
- Sort by type (Documents, Images, Videos, etc.)
- Sort by date (year-month folders)
- Duplicate detection via file hashing
- Dry-run mode to preview changes
- Custom rules via JSON config

**Usage:**
```bash
python file_organizer.py /path/to/folder --organize --dry-run
python file_organizer.py /path/to/folder --find-duplicates
python file_organizer.py --demo
```

---

## All Scripts Include

- Comprehensive error handling
- Detailed logging
- Command-line interface
- Documentation and help text
- No external dependencies (stdlib only)

## License

MIT
