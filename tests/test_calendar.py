from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from unittest.mock import patch

from build_cloud import build, cloud_html
from fx_analyzer import demo_report
from fx_calendar import (SOURCES, CalendarError, calendar_html, calendar_message,
                         collect_calendar, parse_ics, parse_start)
from notify_telegram import message

NOW = datetime(2026, 10, 15, 7, tzinfo=timezone.utc)


def ics(*entries):
    return ('BEGIN:VCALENDAR\nVERSION:2.0\n' + '\n'.join(
        'BEGIN:VEVENT\n'+entry+'\nEND:VEVENT' for entry in entries) + '\nEND:VCALENDAR\n').encode()


def entry(uid, title, start, extra=''):
    return f'UID:{uid}\nSUMMARY:{title}\nDTSTART{start}\n{extra}'


def fixtures():
    return {
        SOURCES['BLS']['feed']: ics(
            entry('old', 'Consumer Price Index', ';TZID=US-Eastern:20261014T083000'),
            entry('next', 'Employment Situation', ';TZID=US-Eastern:20261106T083000')),
        SOURCES['BEA']['feed']: ics(entry('pce', 'Personal Income and Outlays\\, September', ':20261029T123000Z')),
        SOURCES['Eurostat']['feed']: ics(entry('hicp', 'Inflation (HICP)', ';VALUE=DATE:20261016')),
        SOURCES['Fed']['feed']: b'''<h4><a>2026 FOMC Meetings</a></h4><div class="fomc-meeting__month"><strong>October</strong></div><div class="fomc-meeting__date">27-28</div>''',
        SOURCES['ECB']['feed']: b'''<dl><dt>28/10/2026</dt><dd>Governing Council: monetary policy meeting (Day 1)</dd><dt>29/10/2026</dt><dd>Governing Council: monetary policy meeting (Day 2)</dd><dt>25/11/2026</dt><dd>Governing Council: non-monetary policy meeting (Day 2)</dd></dl>''',
    }


class CalendarTests(unittest.TestCase):
    def test_eastern_time_uses_dst_not_a_fixed_offset(self):
        for day, hour in [('20261030', '12:30'), ('20261106', '13:30')]:
            parsed = parse_start(day+'T083000', {'TZID':'US-Eastern'})
            self.assertIn(hour, parsed['at_utc'])

    def test_european_dst_changes_before_us_dst(self):
        early = parse_start('20261023T110000', {'TZID':'Europe/Luxembourg'})
        late = parse_start('20261030T110000', {'TZID':'Europe/Luxembourg'})
        self.assertIn('09:00', early['at_utc'])
        self.assertIn('10:00', late['at_utc'])

    def test_ambiguous_missing_unknown_or_nonexistent_zone_is_not_guessed(self):
        for value, params in [
            ('20261101T013000', {'TZID':'US-Eastern'}),
            ('20260308T023000', {'TZID':'US-Eastern'}),
            ('20261015T083000', {}), ('20261015T083000', {'TZID':'Unknown'})]:
            with self.assertRaises(CalendarError):
                parse_start(value, params)

    def test_folded_summary_and_utc_timestamp(self):
        rows, skipped = parse_ics(ics(entry('pce', 'Personal Income and Out\n lays\\, September', ':20261029T123000Z')), 'BEA')
        self.assertEqual(0, skipped)
        self.assertEqual('Personal Income and Outlays, September', rows[0]['title'])
        self.assertEqual('2026-10-29T12:30:00+00:00', rows[0]['at_utc'])

    def test_date_only_never_becomes_an_invented_release_time(self):
        rows, _ = parse_ics(fixtures()[SOURCES['Eurostat']['feed']], 'Eurostat')
        self.assertEqual('2026-10-16', rows[0]['date'])
        self.assertIsNone(rows[0]['at_utc'])

    def test_cancelled_and_superseded_events_do_not_survive(self):
        body = ics(
            entry('cancel', 'Employment Situation', ':20261016T123000Z', 'SEQUENCE:0'),
            entry('cancel', 'Employment Situation', ':20261016T123000Z', 'SEQUENCE:1\nSTATUS:CANCELLED'),
            entry('move', 'Consumer Price Index', ':20261016T123000Z', 'SEQUENCE:0'),
            entry('move', 'Consumer Price Index', ':20261020T123000Z', 'SEQUENCE:2'),
        )
        rows, _ = parse_ics(body, 'BLS')
        self.assertEqual(1, len(rows))
        self.assertEqual('2026-10-20', rows[0]['date'])

    def test_unsupported_recurrence_is_reported_as_partial(self):
        body = ics(entry('a', 'Employment Situation', ':20261106T133000Z'),
                   entry('b', 'Consumer Price Index', ':20261016T123000Z', 'RRULE:FREQ=DAILY'))
        rows, skipped = parse_ics(body, 'BLS')
        self.assertEqual(1, len(rows))
        self.assertEqual(1, skipped)

    def test_error_page_is_not_an_empty_valid_calendar(self):
        with self.assertRaises(CalendarError):
            parse_ics(b'<html>Access denied</html>', 'BLS')

    def test_five_sources_filter_past_and_nonmonetary_events(self):
        result = collect_calendar(NOW, getter=fixtures().__getitem__)
        self.assertEqual('OK', result['status'])
        self.assertEqual(5, len(result['events']))
        self.assertEqual('2026-10-16', result['events'][0]['date'])
        self.assertEqual(['2026-10-29'], [e['date'] for e in result['events'] if e['source']=='ECB'])
        self.assertEqual(['2026-10-28'], [e['date'] for e in result['events'] if e['source']=='Fed'])

    def test_date_only_today_uses_source_day_not_users_utc_day(self):
        bodies=fixtures()
        bodies[SOURCES['Eurostat']['feed']]=ics(entry('hicp','Inflation (HICP)',';VALUE=DATE:20261016'))
        # Midnight has passed in Luxembourg. A date-only event on the 16th is over.
        result=collect_calendar(datetime(2026,10,16,23,0,tzinfo=timezone.utc), getter=bodies.__getitem__)
        self.assertFalse(any(e['source']=='Eurostat' for e in result['events']))

    def test_failed_source_is_explicit_and_other_sources_still_work(self):
        bodies=fixtures();bodies[SOURCES['BLS']['feed']]=b'<html>Unavailable</html>'
        result=collect_calendar(NOW, getter=bodies.__getitem__)
        self.assertEqual('PARTIAL', result['status'])
        self.assertEqual('UNAVAILABLE', result['sources'][0]['status'])
        self.assertEqual(4, len(result['events']))

    def test_all_failures_never_claim_no_events(self):
        def failed(url):raise RuntimeError('private internal details')
        result=collect_calendar(NOW, getter=failed)
        self.assertEqual('UNAVAILABLE', result['status'])
        text=calendar_message(result,NOW)
        self.assertIn('to ne znači', text[0])
        self.assertNotIn('private internal details',str(result))

    def test_expired_feed_has_its_own_warning(self):
        bodies=fixtures()
        bodies[SOURCES['BLS']['feed']]=ics(entry('old','Consumer Price Index',':20251015T123000Z'))
        result=collect_calendar(NOW,getter=bodies.__getitem__)
        self.assertEqual('OUTDATED', result['sources'][0]['status'])

    def test_calendar_does_not_change_direction_or_core_data_status(self):
        core=demo_report();core.update(source_mode='PUBLIC_DATA',generated_at=NOW.isoformat(),status='OK')
        before=core['outlooks'].copy()
        with tempfile.TemporaryDirectory() as output, patch('build_cloud.collect',return_value=core):
            result=build(output,now=NOW,calendar_getter=lambda url:b'Unavailable')
        self.assertEqual(before,result['outlooks'])
        self.assertEqual('OK',result['status'])
        self.assertEqual('UNAVAILABLE',result['calendar']['status'])

    def test_telegram_lists_three_events_without_sending_and_hides_stale_calendar(self):
        result=collect_calendar(NOW,getter=fixtures().__getitem__)
        text='\n'.join(calendar_message(result,NOW))
        self.assertEqual(3,text.count('•'))
        self.assertIn('satnica nije navedena',text)
        self.assertNotIn('•','\n'.join(calendar_message(result,NOW+timedelta(hours=37))))
        report=demo_report();report.update(source_mode='PUBLIC_DATA',generated_at=NOW.isoformat(),status='OK',calendar=result)
        self.assertIn('Naredne odabrane objave',message(report,now=NOW))

    def test_render_escapes_external_titles_and_keeps_local_time_fallback(self):
        result=collect_calendar(NOW,getter=fixtures().__getitem__)
        result['events'][0]['title']='<script>alert(1)</script>'
        result['events'][0]['url']='javascript:alert(1)'
        html=calendar_html(result)
        self.assertNotIn('<script>',html)
        self.assertNotIn('javascript:',html)
        self.assertIn('&lt;script&gt;',html)
        core=demo_report();core['calendar']=result
        html=cloud_html(core)
        self.assertIn('Intl.DateTimeFormat',html)
        self.assertIn('calendarNotice.hidden=!stale',html)
        self.assertIn('Dnevni presjek',html)


if __name__=='__main__':unittest.main()
