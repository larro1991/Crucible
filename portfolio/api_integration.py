#!/usr/bin/env python3
"""
API Integration Framework
=========================
Connect and sync data between multiple APIs/services.

Features:
- Generic API client with retry logic and rate limiting
- Data transformation between different API formats
- Batch processing with progress tracking
- Detailed logging and error handling

Example: Sync contacts from one CRM to another,
         fetch data from API and save to database, etc.

Usage:
    python api_integration.py --source "https://api1.example.com" --dest "https://api2.example.com"
    python api_integration.py --config config.json
"""

import json
import time
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """Configuration for an API endpoint."""
    base_url: str
    api_key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    rate_limit: float = 1.0  # requests per second
    max_retries: int = 3
    timeout: int = 30


class APIClient:
    """Generic API client with retry logic and rate limiting."""

    def __init__(self, config: APIConfig):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between requests."""
        if self.config.rate_limit > 0:
            min_interval = 1.0 / self.config.rate_limit
            elapsed = time.time() - self.last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers including auth."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'API-Integration/1.0'
        }
        headers.update(self.config.headers)

        if self.config.api_key:
            headers['Authorization'] = f'Bearer {self.config.api_key}'

        return headers

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an API request with retries."""

        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        if params:
            url += '?' + urlencode(params)

        headers = self._build_headers()

        for attempt in range(self.config.max_retries):
            try:
                self._wait_for_rate_limit()

                request = Request(url, method=method, headers=headers)

                if data:
                    request.data = json.dumps(data).encode('utf-8')

                self.last_request_time = time.time()
                self.request_count += 1

                with urlopen(request, timeout=self.config.timeout) as response:
                    body = response.read().decode('utf-8')
                    return json.loads(body) if body else {}

            except HTTPError as e:
                logger.warning(f"HTTP {e.code} on attempt {attempt + 1}: {e.reason}")
                if e.code == 429:  # Rate limited
                    time.sleep(2 ** attempt)
                elif e.code >= 500:  # Server error, retry
                    time.sleep(1)
                else:
                    raise

            except URLError as e:
                logger.warning(f"Network error on attempt {attempt + 1}: {e.reason}")
                time.sleep(1)

        raise Exception(f"Failed after {self.config.max_retries} attempts")

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self.request('GET', endpoint, params=params)

    def post(self, endpoint: str, data: Dict) -> Dict:
        return self.request('POST', endpoint, data=data)

    def put(self, endpoint: str, data: Dict) -> Dict:
        return self.request('PUT', endpoint, data=data)

    def delete(self, endpoint: str) -> Dict:
        return self.request('DELETE', endpoint)


class DataTransformer:
    """Transform data between different API formats."""

    def __init__(self, field_mapping: Dict[str, str]):
        """
        field_mapping: {'source_field': 'dest_field'}
        """
        self.field_mapping = field_mapping

    def transform(self, source_data: Dict) -> Dict:
        """Transform a single record."""
        result = {}
        for source_field, dest_field in self.field_mapping.items():
            if source_field in source_data:
                result[dest_field] = source_data[source_field]
        return result

    def transform_batch(self, records: List[Dict]) -> List[Dict]:
        """Transform multiple records."""
        return [self.transform(r) for r in records]


class SyncJob:
    """Orchestrate data sync between two APIs."""

    def __init__(
        self,
        source_client: APIClient,
        dest_client: APIClient,
        transformer: DataTransformer
    ):
        self.source = source_client
        self.dest = dest_client
        self.transformer = transformer
        self.stats = {
            'records_read': 0,
            'records_written': 0,
            'records_failed': 0,
            'errors': []
        }

    def sync(
        self,
        source_endpoint: str,
        dest_endpoint: str,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """Run the sync job."""
        logger.info(f"Starting sync: {source_endpoint} -> {dest_endpoint}")
        start_time = datetime.now()

        try:
            # Fetch from source
            logger.info("Fetching data from source...")
            source_data = self.source.get(source_endpoint)

            # Handle different response formats
            records = source_data if isinstance(source_data, list) else source_data.get('data', [])
            self.stats['records_read'] = len(records)
            logger.info(f"Read {len(records)} records from source")

            # Transform
            logger.info("Transforming data...")
            transformed = self.transformer.transform_batch(records)

            # Write to destination in batches
            logger.info("Writing to destination...")
            for i in range(0, len(transformed), batch_size):
                batch = transformed[i:i + batch_size]
                try:
                    self.dest.post(dest_endpoint, {'data': batch})
                    self.stats['records_written'] += len(batch)
                    logger.info(f"Wrote batch {i // batch_size + 1} ({len(batch)} records)")
                except Exception as e:
                    self.stats['records_failed'] += len(batch)
                    self.stats['errors'].append(str(e))
                    logger.error(f"Batch failed: {e}")

        except Exception as e:
            self.stats['errors'].append(str(e))
            logger.error(f"Sync failed: {e}")

        self.stats['duration'] = str(datetime.now() - start_time)
        return self.stats


def demo_mode():
    """Run a demonstration with mock data."""
    print("=" * 60)
    print("API INTEGRATION DEMO")
    print("=" * 60)
    print()

    # Simulate source API data
    mock_source_data = [
        {'id': 1, 'first_name': 'John', 'last_name': 'Doe', 'email': 'john@example.com'},
        {'id': 2, 'first_name': 'Jane', 'last_name': 'Smith', 'email': 'jane@example.com'},
        {'id': 3, 'first_name': 'Bob', 'last_name': 'Wilson', 'email': 'bob@example.com'},
    ]

    print("Source Data (CRM A format):")
    print("-" * 40)
    for record in mock_source_data:
        print(f"  {record}")

    # Define transformation
    field_mapping = {
        'first_name': 'firstName',
        'last_name': 'lastName',
        'email': 'emailAddress'
    }

    transformer = DataTransformer(field_mapping)
    transformed = transformer.transform_batch(mock_source_data)

    print()
    print("Transformed Data (CRM B format):")
    print("-" * 40)
    for record in transformed:
        print(f"  {record}")

    print()
    print("Integration Features:")
    print("-" * 40)
    print("  - Automatic retry on failure (configurable)")
    print("  - Rate limiting to respect API limits")
    print("  - Batch processing for large datasets")
    print("  - Field mapping/transformation")
    print("  - Detailed logging and error tracking")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='API Integration Tool')
    parser.add_argument('--demo', action='store_true', help='Run demo mode')
    parser.add_argument('--config', help='Path to config file')

    args = parser.parse_args()

    if args.demo:
        demo_mode()
    elif args.config:
        with open(args.config) as f:
            config = json.load(f)
        print(f"Loaded config: {config}")
        # Real implementation would use config here
    else:
        parser.print_help()
        print("\nRun with --demo to see a demonstration")


if __name__ == '__main__':
    main()
