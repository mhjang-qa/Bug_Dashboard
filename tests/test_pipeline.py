"""Failure-path regression tests. API responses are mocks, never production mutations."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_defect_dashboard as g
import qa_dashboard as q
import notion_api as n


def response(data):
    return io.BytesIO(json.dumps(data).encode())


def page(pid='p', title='fixture', **extra):
    return {'id': pid, 'created_time': '2026-11-24T15:10:00Z', 'properties': {
        '제목': {'type': 'title', 'title': [{'plain_text': title}]}}, **extra}


def http_error(status):
    return urllib.error.HTTPError('https://api.notion.com', status, 'private',
        {'Retry-After': '0'}, response({'code': 'validation_error', 'message': 'SECRET PRIVATE'}))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'NOTION_TOKEN':'fixture-secret', 'NOTION_MAX_ATTEMPTS':'3'})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_TC001_success_version_and_no_global_version_collision(self):
        with patch.dict(os.environ, {'NOTION_VERSION':'2022-06-28'}), patch.object(n.urllib.request, 'urlopen', return_value=response({'object':'list','results':[]})) as call:
            self.assertEqual(n.request('/data_sources/s/query', {})['results'], [])
            req = call.call_args[0][0]
            self.assertEqual(req.get_header('Notion-version'), '2025-09-03')
            self.assertEqual(req.get_method(), 'POST')

    def test_TC002_auth_no_retry_or_private_response(self):
        with patch.object(n.urllib.request, 'urlopen', side_effect=http_error(401)) as call:
            with self.assertRaises(n.NotionError) as ctx: n.request('/users/me')
            self.assertEqual(call.call_count, 1)
            self.assertEqual(ctx.exception.status, 401)
            self.assertNotIn('SECRET',str(ctx.exception))

    def test_TC003_access_error_no_retry(self):
        for status in (400,403,404):
            with self.subTest(status=status), patch.object(n.urllib.request, 'urlopen', side_effect=http_error(status)) as call:
                with self.assertRaises(n.NotionError): n.request('/databases/db')
                self.assertEqual(call.call_count,1)

    def test_TC004_rate_limit_and_network_retry(self):
        for error in (http_error(429),http_error(503),urllib.error.URLError('private host')):
            with patch.object(n.urllib.request,'urlopen',side_effect=[error,response({'object':'list'})]) as call, patch.object(n.time,'sleep') as sleep:
                self.assertEqual(n.request('/data_sources/s/query', {})['object'],'list')
                self.assertEqual(call.call_count,2); sleep.assert_called_once()
        with patch.object(n.urllib.request,'urlopen',side_effect=urllib.error.URLError('private')) as call, patch.object(n.time,'sleep'):
            with self.assertRaises(n.NotionError): n.request('/users/me')
            self.assertEqual(call.call_count,3)

    def test_retry_after_honored_or_deferred(self):
        self.assertEqual(n.retry_delay({'Retry-After':'25'},0),25)
        self.assertEqual(n.retry_delay({},2),4)

    def test_TC009_pagination_and_cursor_validation(self):
        api=SimpleNamespace(notion_request=lambda *a: None)
        responses=[{'data_sources':[{'id':'s'}]}, {'results':[page('one')],'has_more':True,'next_cursor':'c'}, {'results':[page('two')],'has_more':False}]
        with patch.object(api,'notion_request',side_effect=responses) as call,patch.object(n.time,'sleep'):
            self.assertEqual(len(n.query(api,'db','test')),2)
            self.assertEqual(call.call_args_list[-1].args[0],'/data_sources/s/query')
        responses=[{'data_sources':[{'id':'s'}]}, {'results':[],'has_more':True,'next_cursor':None}]
        with patch.object(api,'notion_request',side_effect=responses):
            with self.assertRaises(n.NotionError):n.query(api,'db','test')

    def test_multi_source_does_not_pick_arbitrary_database(self):
        api=SimpleNamespace(notion_request=lambda *a:{'data_sources':[{'id':'s1'},{'id':'s2'}]})
        with self.assertRaises(n.NotionError):n.source_id(api,'db')
        self.assertEqual(n.source_id(api,'db','s2'),'s2')
        with self.assertRaises(n.NotionError):n.source_id(api,'db','unrelated')


class PipelineTests(unittest.TestCase):
    def payload(self,rows=None):
        with patch.object(g,'fetch_report_rows',return_value={}):
            p=g.build_payload(rows or [],30)
        p['sources']={'defects':{'status':'ok','syncedAt':q.now(),'attemptedAt':q.now()}}
        return p

    def test_TC005_real_zero_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=q.sync_source(Path(tmp)/'zero.json',lambda:[])
        self.assertEqual(result['status'],'ok');self.assertEqual(result['data'],[])
        g.validate_payload(self.payload())

    def test_TC006_total_failure_and_preserve_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); output=root/'dashboard.html';output.write_text('LAST SUCCESS')
            args=SimpleNamespace(output=str(output),days=30,publish=True)
            with patch.object(g,'SCRIPT_DIR',root),patch.object(g,'load_env'),patch.object(g,'parse_args',return_value=args),patch.object(g,'fetch_pages',side_effect=n.NotionError(401,'unauthorized')),patch.object(g,'build_payload',return_value=self.payload()),patch.object(q,'extend_payload',side_effect=lambda p,*a:{**p,'sources':{'defects':p['defectSource']}}),patch.object(g,'REPORT_SOURCE_STATUS',{}),patch.object(g,'build_html',return_value='preview'),patch.object(g,'publish_html') as publish:
                self.assertEqual(g.main(),1)
                publish.assert_not_called()
            self.assertEqual(output.read_text(),'LAST SUCCESS')
            self.assertIn('error',(root/'data/last-attempt.json').read_text())

    def test_TC007_partial_database_keeps_other_and_old_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.object(g,'SCRIPT_DIR',root),patch.object(g,'fetch_database_pages',return_value=[page()]),patch.object(g,'REPORT_SOURCE_STATUS',{}):
                first=g.fetch_report_rows()
                def mixed(db,*args):
                    if db==g.REPORT_DB_IDS['GoHanpass']:raise n.NotionError(404,'object_not_found')
                    return [page('new'),page('new2')]
                with patch.object(g,'fetch_database_pages',side_effect=mixed):second=g.fetch_report_rows()
                self.assertEqual(len(second['한패스']),2)
                self.assertEqual(second['GoHanpass'],first['GoHanpass'])
                self.assertEqual(g.REPORT_SOURCE_STATUS['GoHanpass']['status'],'stale')

    def test_TC008_malformed_record_does_not_abort_other_rows(self):
        malformed=page('bad',properties={'제목':{'type':'title','title':123}})
        rows=g.normalize_rows([page(),malformed,page('last')],g.normalize_page)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[1]['title'],'제목 없음')
        rows=g.normalize_rows([page(),{'properties':None},page('last')],g.normalize_page)
        self.assertEqual(len(rows),2);self.assertEqual(rows.skipped,1)

    def test_TC010_service_and_aggregate_conservation(self):
        rows=[g.normalize_page(page('a',title='Hanpass')),g.normalize_page(page('b',title='[G.H] Login'))]
        p=self.payload(rows);g.validate_payload(p)
        self.assertEqual(p['domains']['ALL']['summary']['total'],2)
        self.assertEqual(p['domains']['GoHanpass']['summary']['total'],1)

    def test_TC011_kst_date_and_recent_boundaries(self):
        self.assertEqual(g.date_key('2026-11-24T15:01:00Z'),'2026-11-25')
        self.assertEqual(g.date_key('2026-11-25'),'2026-11-25')
        with patch.object(g,'datetime') as clock:
            clock.now.return_value=datetime(2026,11,25,tzinfo=g.KST)
            clock.fromisoformat.side_effect=datetime.fromisoformat
            self.assertTrue(g.is_recent_date('2026-10-27T00:00:00+09:00',30))
            self.assertFalse(g.is_recent_date('2026-10-26T23:59:59+09:00',30))
            self.assertFalse(g.is_recent_date('2026-11-26T00:00:00+09:00',30))

    def test_TC012_sync_no_browser_credentials_or_fake_dispatch(self):
        html=g.build_html(self.payload())
        self.assertNotIn('syncTokenInput',html)
        self.assertNotIn('api.github.com/repos',html)
        self.assertNotIn('Authorization',html)
        self.assertIn('아직 동기화가 요청된 것은 아닙니다',html)
        self.assertIn('actions/workflows/run_all_notion.yml',html)

    def test_TC013_atomic_write_failure_preserves_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'out.html';path.write_text('GOOD')
            with patch.object(q.os,'replace',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):q.atomic_text(path,'NEW')
            self.assertEqual(path.read_text(),'GOOD')
            self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_TC014_bad_data_cannot_publish(self):
        p=self.payload();p['sources']['defects']['status']='error'
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'dashboard.html';f.write_text(g.build_html(p))
            with patch.object(g,'ensure_publish_repo') as publish:
                with self.assertRaises(g.StepError):g.publish_html(f)
                publish.assert_not_called()

    def test_concurrent_generators_are_locked(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(g,'SCRIPT_DIR',Path(tmp)):
            with g.generation_lock():
                with self.assertRaises(g.StepError):
                    with g.generation_lock():pass

    def test_cache_cannot_cross_database_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.json'
            q.sync_source(path,lambda:[1],identity='source1')
            def fail():raise n.NotionError(404,'object_not_found')
            r=q.sync_source(path,fail,identity='source2')
            self.assertEqual(r['status'],'error');self.assertIsNone(r['data'])

if __name__=='__main__':unittest.main()
