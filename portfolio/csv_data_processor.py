#!/usr/bin/env python3
"""
CSV Data Processor
==================
Automated data cleaning and transformation pipeline.

Features:
- Reads CSV files with automatic encoding detection
- Cleans and normalizes data (trim whitespace, fix dates, handle nulls)
- Generates summary statistics
- Outputs cleaned data + detailed report

Usage:
    python csv_data_processor.py input.csv output.csv
    python csv_data_processor.py input.csv output.csv --report report.txt
"""

import csv
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter


def detect_column_types(rows: List[Dict]) -> Dict[str, str]:
    """Analyze columns and detect data types."""
    if not rows:
        return {}

    types = {}
    for col in rows[0].keys():
        values = [r[col] for r in rows if r[col]]

        if not values:
            types[col] = 'empty'
            continue

        # Check if numeric
        numeric_count = sum(1 for v in values if is_numeric(v))
        if numeric_count / len(values) > 0.8:
            types[col] = 'numeric'
            continue

        # Check if date
        date_count = sum(1 for v in values if is_date(v))
        if date_count / len(values) > 0.8:
            types[col] = 'date'
            continue

        types[col] = 'text'

    return types


def is_numeric(value: str) -> bool:
    """Check if value is numeric."""
    try:
        float(value.replace(',', '').replace('$', ''))
        return True
    except (ValueError, AttributeError):
        return False


def is_date(value: str) -> bool:
    """Check if value looks like a date."""
    date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y']
    for fmt in date_formats:
        try:
            datetime.strptime(value.strip(), fmt)
            return True
        except ValueError:
            continue
    return False


def clean_value(value: str, col_type: str) -> str:
    """Clean a single value based on its type."""
    if not value or value.lower() in ('null', 'none', 'n/a', 'na', ''):
        return ''

    value = value.strip()

    if col_type == 'numeric':
        # Remove currency symbols and commas
        cleaned = value.replace('$', '').replace(',', '').strip()
        try:
            return str(float(cleaned))
        except ValueError:
            return value

    elif col_type == 'date':
        # Normalize to ISO format
        for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y']:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return value

    else:
        # Text: normalize whitespace
        return ' '.join(value.split())


def process_csv(input_path: str, output_path: str) -> Dict[str, Any]:
    """Process CSV file and return statistics."""
    stats = {
        'input_file': input_path,
        'output_file': output_path,
        'rows_read': 0,
        'rows_written': 0,
        'columns': [],
        'column_types': {},
        'null_counts': {},
        'issues_fixed': 0,
        'processing_time': None
    }

    start_time = datetime.now()

    # Read input
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        stats['columns'] = reader.fieldnames or []

    stats['rows_read'] = len(rows)

    if not rows:
        print("Warning: Empty file")
        return stats

    # Detect types
    col_types = detect_column_types(rows)
    stats['column_types'] = col_types

    # Clean data
    cleaned_rows = []
    for row in rows:
        cleaned_row = {}
        for col, value in row.items():
            original = value
            cleaned = clean_value(value, col_types.get(col, 'text'))
            cleaned_row[col] = cleaned

            if original != cleaned:
                stats['issues_fixed'] += 1

            if not cleaned:
                stats['null_counts'][col] = stats['null_counts'].get(col, 0) + 1

        cleaned_rows.append(cleaned_row)

    # Write output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=stats['columns'])
        writer.writeheader()
        writer.writerows(cleaned_rows)

    stats['rows_written'] = len(cleaned_rows)
    stats['processing_time'] = str(datetime.now() - start_time)

    return stats


def generate_report(stats: Dict[str, Any]) -> str:
    """Generate human-readable report."""
    lines = [
        "=" * 60,
        "CSV DATA PROCESSING REPORT",
        "=" * 60,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "INPUT/OUTPUT",
        "-" * 40,
        f"Input file:  {stats['input_file']}",
        f"Output file: {stats['output_file']}",
        f"Rows read:   {stats['rows_read']}",
        f"Rows written: {stats['rows_written']}",
        "",
        "COLUMN ANALYSIS",
        "-" * 40,
    ]

    for col in stats['columns']:
        col_type = stats['column_types'].get(col, 'unknown')
        nulls = stats['null_counts'].get(col, 0)
        lines.append(f"  {col}: {col_type} ({nulls} nulls)")

    lines.extend([
        "",
        "PROCESSING SUMMARY",
        "-" * 40,
        f"Issues fixed: {stats['issues_fixed']}",
        f"Processing time: {stats['processing_time']}",
        "",
        "=" * 60,
    ])

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Clean and process CSV data')
    parser.add_argument('input', help='Input CSV file')
    parser.add_argument('output', help='Output CSV file')
    parser.add_argument('--report', '-r', help='Save report to file')

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)

    print(f"Processing {args.input}...")
    stats = process_csv(args.input, args.output)

    report = generate_report(stats)
    print(report)

    if args.report:
        with open(args.report, 'w') as f:
            f.write(report)
        print(f"\nReport saved to {args.report}")

    print(f"\nCleaned data saved to {args.output}")


if __name__ == '__main__':
    main()
