"""
Test case loader for Agent Regression.

This module handles loading test cases from various sources (CSV, JSON, etc.).
"""

import csv
from pathlib import Path
from typing import List, Optional

from .models import TestCase


def load_from_csv(file_path: str) -> List[TestCase]:
    """
    Load test cases from a CSV file.
    
    Args:
        file_path: Path to the CSV file containing test cases
        
    Returns:
        List of TestCase objects
        
    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        ValueError: If the CSV format is invalid
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Test case file not found: {file_path}")
    
    cases = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Build metadata from standard + extended columns
            meta: dict = {
                'category': row.get('category', 'general'),
                'severity': row.get('severity', 'S2'),
            }
            # P1 extended columns (optional – backwards compatible)
            if row.get('owner'):
                meta['owner'] = row['owner']
            if row.get('tags'):
                meta['tags'] = [t.strip() for t in row['tags'].split(';') if t.strip()]
            if row.get('min_pass_rate'):
                try:
                    meta['min_pass_rate'] = float(row['min_pass_rate'])
                except ValueError:
                    pass

            case = TestCase(
                case_id=row.get('case_id', ''),
                name=row.get('name', ''),
                input_prompt=row.get('input_prompt', ''),
                expected_output=row.get('expected_output'),
                metadata=meta,
            )
            cases.append(case)
    
    return cases


def load_from_directory(directory_path: str, pattern: str = "*.csv") -> List[TestCase]:
    """
    Load all test cases from CSV files in a directory.
    
    Args:
        directory_path: Path to directory containing test case files
        pattern: Glob pattern for matching files (default: *.csv)
        
    Returns:
        Combined list of TestCase objects from all files
    """
    path = Path(directory_path)
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory_path}")
    
    all_cases = []
    for file_path in path.glob(pattern):
        cases = load_from_csv(str(file_path))
        all_cases.extend(cases)
    
    return all_cases
