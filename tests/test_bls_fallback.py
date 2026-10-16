from datetime import datetime, timedelta, timezone
import io
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from fx_calendar import (SOURCES, CalendarError, bls_fallback, collect_calendar,
                         fetch_calendar, parse_bls_month)

NOW = datetime(2026, 10, 16, 14, tzinfo=timezone.utc)
OCT = 'https://www.bls.gov/schedule/2026/10_sched_list.htm'
NOV = 'https://www.bls.gov/schedule/2026/11_sched_list.htm'


def month(day, title='Employment Situation', clock='08:30 AM'):
    return f'''<html><table class="release-list"><thead><tr><th>Date</th><th>Time</th><th>Release</th></tr></thead>
<tbody><tr><td>{day}</td><td>{clock}</td><td><strong>{title}</strong> for the previous period</td></tr></tbody></table>
<p>NOTE: All times on calendar are Eastern Time.</p></html>'''.encode()


class BlsFallbackTests(unittest.TestCase):
    def test_monthly_source_preserves_dst_date_and_official_url(self):
        october, skipped = parse_bls_month(month('Friday, October 30, 2026'), 2026, 10)
        november, _ = parse_bls_month(month('Friday, November 6, 2026'), 2026, 11)
        self.assertEqual(0, skipped)
        self.assertEqual('2026-10-30T12:30:00+00:00', october[0]['at_utc'])
        self.assertEqual('2026-11-06T13:30:00+00:00', november[0]['at_utc'])
        self.assertEqual(NOV, november[0]['url'])

    def test_missing_time_is_date_only_but_invalid_time_is_counted(self):
        rows, skipped = parse_bls_month(month('Friday, October 30, 2026', clock=''), 2026, 10)
        self.assertIsNone(rows[0]['at_utc'])
        self.assertEqual(0, skipped)
        rows, skipped = parse_bls_month(month('Friday, October 30, 2026', clock='TBA'), 2026, 10)
        self.assertEqual([], rows)
        self.assertEqual(1, skipped)

    def test_wrong_month_error_html_or_missing_timezone_is_not_valid_coverage(self):
        for body in [month('Friday, November 6, 2026'), b'<html>Access denied</html>',
                     month('Friday, October 30, 2026').replace(b'Eastern Time', b'local time')]:
            with self.assertRaises(CalendarError):
                parse_bls_month(body, 2026, 10)

    def test_valid_month_without_selected_release_can_have_zero_events(self):
        rows, skipped = parse_bls_month(month('Friday, October 30, 2026', title='Metropolitan Area Employment'), 2026, 10)
        self.assertEqual(([], 0), (rows, skipped))

    def test_malformed_row_does_not_masquerade_as_complete_coverage(self):
        body = month('Friday, October 30, 2026').replace(b'</tbody>', b'<tr><td>Incomplete</td><td>Consumer Price Index</td></tr></tbody>')
        rows, skipped = parse_bls_month(body, 2026, 10)
        self.assertEqual(1, len(rows))
        self.assertEqual(1, skipped)

    def test_failure_of_primary_uses_two_official_months(self):
        bodies = {OCT: month('Friday, October 30, 2026', title='Employment Cost Index'),
                  NOV: month('Friday, November 6, 2026')}
        result = collect_calendar(NOW, getter=bodies.__getitem__)
        bls = next(source for source in result['sources'] if source['source']=='BLS')
        self.assertEqual('OK', bls['status'])
        self.assertTrue(bls['fallback_used'])
        self.assertEqual([OCT, NOV], bls['loaded_urls'])
        self.assertEqual(2, bls['events'])

    def test_unavailable_month_is_explicit_partial_not_complete_coverage(self):
        result = collect_calendar(NOW, getter={OCT: month('Friday, October 30, 2026')}.__getitem__)
        bls = result['sources'][0]
        self.assertEqual('PARTIAL', bls['status'])
        self.assertEqual([NOV], bls['unavailable_urls'])
        self.assertEqual(1, bls['events'])

    def test_fallback_crosses_new_year(self):
        now = datetime(2026, 12, 20, 15, tzinfo=timezone.utc)
        bodies = {
            'https://www.bls.gov/schedule/2026/12_sched_list.htm': month('Friday, December 11, 2026'),
            'https://www.bls.gov/schedule/2027/01_sched_list.htm': month('Friday, January 8, 2027')}
        rows, skipped, meta = bls_fallback(now, now+timedelta(days=30), bodies.__getitem__)
        self.assertEqual(2, len(rows))
        self.assertEqual(0, skipped)
        self.assertEqual([], meta['unavailable_urls'])
        self.assertEqual('2027-01-19', meta['coverage_end'])

    def test_transient_errors_retry_once_but_forbidden_is_not_retried(self):
        url = SOURCES['BLS']['feed']
        for error in [HTTPError(url, 503, 'Unavailable', {}, None), URLError('timeout')]:
            opener = Mock()
            opener.open.side_effect = [error, io.BytesIO(b'calendar')]
            with patch('fx_calendar.build_opener', return_value=opener), patch('fx_calendar.time.sleep'):
                self.assertEqual(b'calendar', fetch_calendar(url))
            self.assertEqual(2, opener.open.call_count)
        opener = Mock()
        opener.open.side_effect = HTTPError(url, 403, 'Forbidden', {}, None)
        with patch('fx_calendar.build_opener', return_value=opener), patch('fx_calendar.time.sleep'):
            with self.assertRaises(HTTPError):
                fetch_calendar(url)
        self.assertEqual(1, opener.open.call_count)


if __name__ == '__main__':
    unittest.main()
