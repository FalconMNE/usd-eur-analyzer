from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_cloud
from fx_analyzer import demo_report
from notify_telegram import message, send

NOW=datetime(2026,10,14,18,0,tzinfo=timezone.utc)


def report():
    r=demo_report()
    r.update(source_mode='PUBLIC_DATA',generated_at=NOW.isoformat(),status='OK',reference_date='2026-10-14')
    return r


class CloudTests(unittest.TestCase):
    def test_report_is_mobile_and_has_no_pc_start_instructions(self):
        html=build_cloud.cloud_html(report())
        self.assertIn('max-width:760px',html)
        self.assertNotIn('01_Analiza_USD_EUR.cmd',html)
        self.assertIn("cards.style.display=stale?'none':''",html)
        self.assertIn('setInterval(freshness,60000)',html)

    def test_failed_refresh_replaces_old_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('build_cloud.collect',return_value=report()):
                build_cloud.build(tmp,now=NOW)
            with patch('build_cloud.collect',side_effect=RuntimeError('internal detail')):
                result=build_cloud.build(tmp,now=NOW+timedelta(days=1))
            saved=json.loads((Path(tmp)/'report.json').read_text())
            self.assertEqual('FAILED',saved['status'])
            self.assertEqual([],saved['outlooks'])
            self.assertNotIn('internal detail',(Path(tmp)/'index.html').read_text())
            self.assertIsNone(result.get('eur_per_usd'))

    def test_build_contains_only_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('build_cloud.collect',return_value=report()):
                build_cloud.build(tmp,now=NOW)
            self.assertEqual({'.nojekyll','index.html','report.json'},{p.name for p in Path(tmp).iterdir()})

    def test_live_message_has_rate_units_dates_and_horizons(self):
        text=message(report(),now=NOW)
        for value in ['1 USD =','EUR (ECB referenca','2026-10-14','Sedmica:','Mjesec:','Zbir nije vjerovatnoća']:
            self.assertIn(value,text)

    def test_old_demo_missing_future_and_naive_reports_never_send_direction(self):
        for changes in [
            {'generated_at':(NOW-timedelta(hours=37)).isoformat()},
            {'source_mode':'DEMO'}, {'status':'INSUFFICIENT_DATA'},
            {'generated_at':(NOW+timedelta(days=1)).isoformat()},
            {'generated_at':'2026-10-14T18:00:00'}, {'generated_at':'invalid'}]:
            with self.subTest(changes=changes):
                r=report();r.update(changes)
                text=message(r,now=NOW)
                self.assertIn('Nema važeće nove procjene',text)
                self.assertNotIn('Sedmica:',text)

    def test_site_links_require_https_and_no_embedded_credentials(self):
        for url in ['javascript:alert(1)','http://example.com','https://token@example.com','https://example.com\nBAD']:
            with self.assertRaises(ValueError):message(report(),url,now=NOW)

    def test_send_calls_only_telegram_private_chat_without_formatting(self):
        class FakeOpener:
            def open(self,req,timeout):
                self.req=req;self.timeout=timeout
                return io.BytesIO(b'{"ok":true,"result":{"message_id":42}}')
        opener=FakeOpener()
        send('sample', '123456:'+'x'*30, '1234567',opener)
        self.assertTrue(opener.req.full_url.startswith('https://api.telegram.org/bot'))
        body=json.loads(opener.req.data)
        self.assertEqual('1234567',body['chat_id'])
        self.assertNotIn('parse_mode',body)
        self.assertEqual(20,opener.timeout)
        for recipient in ['-1234567','@channel','bad']:
            with self.assertRaises(ValueError):send('sample','123456:'+'x'*30,recipient,opener)

    def test_delivery_error_never_contains_token_and_is_not_retried(self):
        class BadOpener:
            calls=0
            def open(self,req,timeout):
                self.calls+=1
                raise RuntimeError(req.full_url)
        opener=BadOpener();token='123456:'+'secret'*6
        with self.assertRaises(RuntimeError) as caught:send('sample',token,'12345',opener)
        self.assertNotIn(token,str(caught.exception))
        self.assertEqual(1,opener.calls)


if __name__=='__main__':unittest.main()
