"""Opt-in read-only API integration; keep separate from default offline tests."""
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_defect_dashboard as g

@unittest.skipUnless(os.getenv('RUN_NOTION_INTEGRATION') == '1', 'Set RUN_NOTION_INTEGRATION=1 with server-side NOTION_TOKEN')
class LiveNotionTests(unittest.TestCase):
    def test_TC016_real_source_and_dashboard_reconcile(self):
        pages = g.fetch_pages()
        rows = g.normalize_rows(pages, g.normalize_page)
        self.assertEqual(rows.skipped, 0)
        self.assertEqual(len(pages),len(rows))
        self.assertEqual(len({p['id'] for p in pages}), len(pages))
        payload = g.build_payload(rows,30)
        g.validate_payload(payload)
        self.assertEqual(payload['domains']['ALL']['summary']['total'],len(pages))
        for domain in ('한패스','GoHanpass'):
            self.assertEqual(payload['domains'][domain]['summary']['total'],sum(r['domain']==domain for r in rows))
        self.assertTrue(all(s['status']=='ok' for s in g.REPORT_SOURCE_STATUS.values()))
        print('LIVE_RECONCILIATION', {k:v['summary']['total'] for k,v in payload['domains'].items()})

if __name__=='__main__':unittest.main()
