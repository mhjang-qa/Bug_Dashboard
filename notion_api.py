"""Read-only Notion transport. Never include response bodies or credentials in errors."""
from __future__ import annotations
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

VERSION = '2025-09-03'  # First version supporting database/data-source separation.

class NotionError(RuntimeError):
    def __init__(self, status=0, code='network_error'):
        self.status = status
        self.code = code if re.fullmatch(r'[a-z_]+', str(code)) else 'api_error'
        super().__init__(f'Notion status={status} code={self.code}')


def retry_delay(headers, attempt):
    raw = headers.get('Retry-After', '')
    try:
        return max(0., float(raw))
    except ValueError:
        try:
            return max(0., (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError):
            return min(2 ** attempt, 16)


def request(path, payload=None):
    token = os.getenv('NOTION_TOKEN', '').strip()
    if not token:
        raise NotionError(401, 'missing_token')
    version = os.getenv('DEFECT_NOTION_VERSION', VERSION)
    if version < VERSION:
        raise NotionError(400, 'unsupported_api_version')
    retries = max(1, min(int(os.getenv('NOTION_MAX_ATTEMPTS', '4')), 6))
    for attempt in range(retries):
        req = urllib.request.Request(
            'https://api.notion.com/v1' + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Authorization': 'Bearer ' + token, 'Notion-Version': version,
                     'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                result = json.load(response)
            if not isinstance(result, dict) or result.get('object') == 'error':
                raise NotionError(200, 'invalid_response')
            return result
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read())
            except (ValueError, OSError):
                error = {}
            code = error.get('code', 'api_error') if isinstance(error, dict) else 'api_error'
            print(f'[notion] status={exc.code} code={NotionError(exc.code, code).code} attempt={attempt+1}', flush=True)
            if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 == retries:
                raise NotionError(exc.code, code) from None
            delay = retry_delay(exc.headers, attempt)
            # Never retry earlier than Retry-After. Excessive waits fail this run.
            if delay > 60:
                raise NotionError(exc.code, 'retry_deferred') from None
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError):
            print(f'[notion] status=0 code=network_error attempt={attempt+1}', flush=True)
            if attempt + 1 == retries:
                raise NotionError() from None
            time.sleep(min(2 ** attempt, 16))
        except (ValueError, UnicodeDecodeError):
            raise NotionError(200, 'invalid_json') from None


def source_id(api, database_id, explicit=''):
    db = api.notion_request('/databases/' + database_id)
    sources = db.get('data_sources')
    if not isinstance(sources, list) or not sources:
        raise NotionError(200, 'missing_data_source')
    ids = [s['id'] for s in sources]
    if explicit:
        canonical = explicit.replace('-', '')
        matches = [i for i in ids if i.replace('-', '') == canonical]
        if len(matches) != 1:
            raise NotionError(400, 'data_source_mismatch')
        return matches[0]
    if len(ids) != 1:
        raise NotionError(400, 'ambiguous_data_source')
    return ids[0]


def query(api, database_id, label, explicit=''):
    sid = source_id(api, database_id, explicit)
    print(f'[notion] database={database_id} source={sid} label={label}', flush=True)
    pages, seen_ids, cursors = [], set(), set()
    payload = {'page_size': 100}
    while True:
        data = api.notion_request('/data_sources/' + sid + '/query', payload)
        chunk = data.get('results')
        if not isinstance(chunk, list) or not isinstance(data.get('has_more'), bool):
            raise NotionError(200, 'invalid_pagination')
        for page in chunk:
            if not isinstance(page, dict) or not page.get('id') or not isinstance(page.get('properties'), dict):
                raise NotionError(200, 'invalid_page')
            if page['id'] in seen_ids:
                raise NotionError(200, 'duplicate_page')
            seen_ids.add(page['id']); pages.append(page)
        print(f'[notion] label={label} status=200 page={len(cursors)+1} rows={len(chunk)} total={len(pages)}', flush=True)
        if not data['has_more']:
            return pages
        cursor = data.get('next_cursor')
        if not isinstance(cursor, str) or not cursor or cursor in cursors:
            raise NotionError(200, 'invalid_cursor')
        cursors.add(cursor); payload['start_cursor'] = cursor
        time.sleep(.35)
