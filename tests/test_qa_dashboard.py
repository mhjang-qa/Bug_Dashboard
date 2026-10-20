"""Boundary cases use fixtures only in tests; production never uses sample data."""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_defect_dashboard as legacy
import qa_dashboard as qa


def task(status, start=None, end=None):
    return {'id': 'test-id', 'url': 'https://www.notion.so/test', 'properties': {
        '이름': {'type': 'title', 'title': [{'plain_text': 'Test fixture'}]},
        '선택': {'type': 'select', 'select': {'name': status}},
        '날짜': {'type': 'date', 'date': {'start': start, 'end': end} if start else None},
        'TC 개수': {'type': 'number', 'number': None},
    }}


class TaskDateTests(unittest.TestCase):
    def parse(self, status, start=None, end=None):
        return qa.normalize_tasks([task(status, start, end)], legacy.plain_text, today=date(2026, 10, 20))[0]

    def test_due_date_boundaries(self):
        self.assertTrue(self.parse('테스트 진행중', '2026-10-14', '2026-10-19')['overdue'])
        self.assertFalse(self.parse('테스트 진행중', '2026-10-14', '2026-10-20')['overdue'])
        self.assertFalse(self.parse('테스트 진행중', '2026-08-01')['overdue'])
        self.assertFalse(self.parse('테스트 예정')['overdue'])

    def test_completed_stopped_and_partial(self):
        for state in ('태스트 완료', '테스트 중지'):
            self.assertFalse(self.parse(state, '2026-01-01', '2026-01-02')['overdue'])
        partial = self.parse('1차 테스트 완료', '2026-01-01', '2026-01-02')
        self.assertEqual(partial['state'], '단계 완료')
        self.assertTrue(partial['overdue'])

    def test_unknown_state_does_not_guess(self):
        self.assertEqual(self.parse('새로운 상태')['state'], '분류 미확인')

    def test_completed_future_schedule_warning(self):
        self.assertTrue(self.parse('태스트 완료', '2026-10-21', '2026-10-27')['warnings'])

    def test_kst_date_and_missing_fields(self):
        self.assertEqual(qa.day('2026-10-19T16:00:00Z'), '2026-10-20')
        parsed = self.parse('테스트 예정')
        self.assertEqual(parsed['owners'], [])
        self.assertIsNone(parsed['tcCount'])
        self.assertNotIn('progress', parsed)
        self.assertNotIn('service', parsed)


class ResilienceTests(unittest.TestCase):
    def test_stale_cache_retains_last_success_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'source.json'
            original = qa.sync_source(path, lambda: {'rows': [1]})
            before = path.read_bytes()
            def fail(): raise RuntimeError('private server response')
            stale = qa.sync_source(path, fail)
            self.assertEqual(stale['status'], 'stale')
            self.assertEqual(stale['data'], original['data'])
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn('private', json.dumps(stale))
            other = qa.sync_source(Path(tmp)/'other.json', lambda: {'rows': [2]})
            self.assertEqual(other['status'], 'ok')

    def test_no_cache_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(): raise RuntimeError('fail')
            result = qa.sync_source(Path(tmp)/'missing.json', fail)
            self.assertEqual(result['status'], 'error')
            self.assertIsNone(result['data'])

    def test_schema_change_stops_mapping(self):
        with self.assertRaises(ValueError):
            qa.validate_schema({'properties': {'날짜': {'type': 'rich_text'}}}, {'날짜': 'date'})

    def test_risk_is_not_guessed(self):
        self.assertIsNone(qa.release_risk()['level'])

    def test_defect_completion_uses_existing_project_rule(self):
        rows = []
        for status in ('개발 완료 (Dev Done)', '완료 (Done)', '추후 수정 백로그 이관', 'QA 검증 -회귀 (QA Verification)'):
            rows.append({'title':'test', 'url':'https://www.notion.so/test', 'status':status,
                         'stage':legacy.normalize_status(status), 'severity':'Critical',
                         'version':'test', 'domain':'한패스','createdDate':'2026-10-01'})
        metrics = qa.quality_metrics(rows, legacy, today=date(2026,10,20))
        self.assertEqual(metrics['unresolvedCritical'], 2)
        self.assertEqual(metrics['awaitingVerification'], 1)


class RenderingTests(unittest.TestCase):
    def test_json_cannot_terminate_script_element(self):
        import re
        with patch.object(legacy, 'fetch_report_rows', return_value={}):
            payload = legacy.build_payload([], 30)
        payload['untrustedTitle'] = '</SCRIPT><script>alert(1)</script>'
        html = legacy.build_html(payload)
        raw = re.search(r'<script id="dashboard-data" type="application/json">(.*?)</script>', html, re.S)[1]
        self.assertEqual(json.loads(raw)['untrustedTitle'], payload['untrustedTitle'])
        self.assertNotIn('</SCRIPT>', raw)

    def test_new_source_failures_preserve_defect_aggregates(self):
        from types import SimpleNamespace
        import copy
        with patch.object(legacy, 'fetch_report_rows', return_value={}):
            payload = legacy.build_payload([], 30)
        before = copy.deepcopy(payload['domains'])
        failed = {'status': 'error', 'data': None, 'syncedAt': None}
        with patch.object(qa, 'sync_source', return_value=failed):
            qa.extend_payload(payload, [], SimpleNamespace(**vars(legacy)))
        for domain in before:
            for key in before[domain]:
                if key == 'summary':
                    self.assertEqual({k:payload['domains'][domain][key][k] for k in before[domain][key]}, before[domain][key])
                else:
                    self.assertEqual(payload['domains'][domain][key],before[domain][key])
        self.assertIn('QA DASHBOARD',legacy.build_html(payload))


if __name__ == '__main__':
    unittest.main()
