"""Fictional text fixtures; no article bodies or credentials are stored here."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import unittest
import xml.etree.ElementTree as ET

from build_cloud import cloud_html
from fx_analyzer import demo_report
from fx_news import (IBKR_PUBLISHER, NewsError, assess_news, combine_outlooks,
                     extract_events, parse_feed)
from notify_telegram import message

NOW = datetime(2026, 10, 16, 14, tzinfo=timezone.utc)
ARTICLE = 'https://www.interactivebrokers.com/campus/traders-insight/example/'


def rss(*items):
    channel = ET.Element('channel')
    for values in items:
        item = ET.SubElement(channel, 'item')
        defaults = {'title': 'US economic update', 'link': ARTICLE,
                    'pubDate': format_datetime(NOW - timedelta(hours=1))}
        defaults.update(values)
        for key, value in defaults.items():
            ET.SubElement(item, key).text = value
    root = ET.Element('rss')
    root.append(channel)
    return ET.tostring(root, encoding='utf-8')


def parsed(text, **values):
    return parse_feed(rss({'description': text, **values}), IBKR_PUBLISHER, NOW)


def context(text):
    return assess_news(parsed(text), NOW)


class NewsTests(unittest.TestCase):
    def test_us_and_eurozone_surprises_have_opposite_currency_signs(self):
        for text, direction in [
            ('US inflation was above expectations.', 1),
            ('US inflation was below consensus.', -1),
            ('Eurozone inflation was above expectations.', -1),
            ('Eurozone inflation was below consensus.', 1),
            ('US retail sales beat estimates.', 1),
            ('Eurozone GDP missed forecasts.', 1),
        ]:
            with self.subTest(text=text):
                features = extract_events('', text, IBKR_PUBLISHER)
                self.assertEqual([direction], [f['usd_direction'] for f in features])
                self.assertEqual('REPORTED_SURPRISE', features[0]['kind'])

    def test_unemployment_and_claims_invert_the_employment_channel(self):
        for text, direction in [
            ('US payrolls were above expectations.', 1),
            ('US unemployment was above expectations.', -1),
            ('US jobless claims were below consensus.', 1),
            ('Eurozone unemployment was above expectations.', 1),
        ]:
            with self.subTest(text=text):
                self.assertEqual(direction, extract_events('', text, IBKR_PUBLISHER)[0]['usd_direction'])

    def test_actual_decisions_are_distinct_from_commentary(self):
        for publisher, text, kind, direction in [
            ('Federal Reserve', 'The Committee decided to lower the target range for the federal funds rate.', 'OFFICIAL_DECISION', -1),
            ('ECB', 'The Governing Council raised the deposit facility rate.', 'OFFICIAL_DECISION', -1),
            (IBKR_PUBLISHER, 'The Fed has raised interest rates.', 'REPORTED_DECISION', 1),
        ]:
            with self.subTest(text=text):
                event = extract_events('', text, publisher)[0]
                self.assertEqual((kind, direction), (event['kind'], event['usd_direction']))

    def test_forecasts_negation_past_and_holds_are_not_decisions(self):
        for text in [
            'The Fed will cut policy rates.',
            'The Fed could raise interest rates.',
            'If the ECB cut interest rates, the euro could fall.',
            'The Fed did not raise interest rates.',
            'The Fed is expected to cut interest rates.',
            'Economists expect the Fed to cut interest rates.',
            'The Fed raised interest rates last year.',
            'In 2022 the Fed raised interest rates.',
            'The Fed held interest rates unchanged.',
            'The Fed plans to cut interest rates.',
        ]:
            with self.subTest(text=text):
                self.assertEqual([], extract_events('', text, IBKR_PUBLISHER, NOW))

    def test_described_expectation_change_is_not_an_official_decision(self):
        events = extract_events('', 'Credit stress is reducing odds of Fed hikes.', IBKR_PUBLISHER)
        self.assertEqual('COMMENTARY_EXPECTATION', events[0]['kind'])
        self.assertEqual(-1, events[0]['usd_direction'])
        self.assertEqual([], extract_events('', 'Credit stress could be reducing odds of Fed hikes.', IBKR_PUBLISHER))
        self.assertEqual([], extract_events('', 'Credit stress is not reducing odds of Fed hikes.', IBKR_PUBLISHER))

    def test_ambiguous_or_unrelated_comparisons_are_left_unclassified(self):
        for text in [
            'US inflation rose by 0.2 percent.',
            'US inflation was not above expectations.',
            'US inflation could be above expectations tomorrow.',
            'US inflation was above expectations last year.',
            'US inflation and retail sales were above expectations.',
            'US payrolls and unemployment were above expectations.',
            'US inflation is high but bank earnings beat estimates.',
            'Canadian inflation was above expectations.',
            'Inflation was above expectations, according to analysts speaking to us.',
            'US and eurozone inflation were above expectations.',
        ]:
            with self.subTest(text=text):
                self.assertEqual([], extract_events('', text, IBKR_PUBLISHER))

    def test_region_can_come_from_heading_but_not_override_another_economy(self):
        events = extract_events('US CPI report', 'Inflation was above expectations.\nCanadian inflation was below consensus.', IBKR_PUBLISHER)
        self.assertEqual(1, len(events))
        self.assertEqual('US', events[0]['region'])
        mixed = extract_events('', 'US inflation was above expectations. Eurozone inflation was below expectations.', IBKR_PUBLISHER)
        self.assertEqual({'US', 'EU'}, {f['region'] for f in mixed})

    def test_full_rss_text_affects_analysis_without_being_republished(self):
        body = rss({'title': 'US economic update',
                    'description': 'A review of recent data.',
                    '{http://purl.org/rss/1.0/modules/content/}encoded': '<p>US inflation was above consensus.</p><p>Body-only marker: PRIVATE_FIXTURE_TEXT.</p>',
                    '{http://purl.org/dc/elements/1.1/}creator': 'Example Author'})
        items = parse_feed(body, IBKR_PUBLISHER, NOW)
        self.assertEqual('RSS_FULL_TEXT', items[0]['text_scope'])
        self.assertEqual('Example Author', items[0]['author'])
        self.assertEqual(1, items[0]['events'][0]['usd_direction'])
        self.assertNotIn('PRIVATE_FIXTURE_TEXT', json.dumps(items))

    def test_scripts_and_disclosure_lines_do_not_become_features(self):
        items = parsed('<p>General update.</p><script>US inflation was above consensus.</script><p>Disclosure: The Fed raised interest rates.</p>', title='Fed update')
        self.assertEqual([], items[0]['events'])

    def test_prediction_market_and_education_items_are_not_observed_releases(self):
        for category in ['Prediction Markets', 'Trading Education']:
            self.assertEqual([], parsed('US inflation was above expectations.', category=category))
        self.assertEqual([], parsed('Bank earnings beat expectations.', title='Bank profits'))

    def test_publisher_links_dates_and_duplicate_tracking_links_are_checked(self):
        items = parse_feed(rss(
            {'description': 'US inflation was above expectations.'},
            {'title': 'US inflation update', 'link': ARTICLE+'?utm_source=duplicate', 'description': 'US inflation was above expectations.'},
            {'title': 'Fed update', 'link': 'https://example.org/other/'},
            {'title': 'Fed update two', 'link': 'https://www.interactivebrokers.com:8080/campus/traders-insight/other/'},
            {'title': 'Future Fed update', 'link': ARTICLE+'future/', 'pubDate': format_datetime(NOW+timedelta(minutes=1))},
            {'title': 'Old Fed update', 'link': ARTICLE+'old/', 'pubDate': format_datetime(NOW-timedelta(days=31))},
            {'title': 'Naive Fed update', 'link': ARTICLE+'naive/', 'pubDate': 'Fri, 16 Oct 2026 10:00:00'},
        ), IBKR_PUBLISHER, NOW)
        self.assertEqual(1, len(items))

    def test_invalid_xml_dtd_and_oversized_feed_are_rejected(self):
        for body in [b'<html>Error</html>', b'<!DOCTYPE rss><rss><channel/></rss>', b'<!ENTITY bad "x"><rss/>', b'x'*4_000_001]:
            with self.assertRaises(NewsError):
                parse_feed(body, IBKR_PUBLISHER, NOW)

    def test_only_fresh_items_influence_the_context(self):
        items = parsed('US inflation was above consensus.')
        items += parsed('Eurozone inflation was above expectations.', link=ARTICLE+'old/', pubDate=format_datetime(NOW-timedelta(hours=73)))
        result = assess_news(items, NOW)
        self.assertEqual(1, result['active_articles'])
        self.assertEqual('USD_UP_BIAS', result['bias'])
        future = deepcopy(items[0]); future['published_at'] = (NOW+timedelta(hours=1)).isoformat()
        self.assertEqual('UNCLEAR', assess_news([future], NOW)['bias'])

    def test_articles_do_not_multiply_a_topic_vote_and_conflicts_remain_visible(self):
        items = parsed('US inflation was above consensus.')
        items += parsed('US CPI beat expectations.', title='US CPI', link=ARTICLE+'second/')
        first = assess_news(items, NOW)
        self.assertEqual(1, first['event_groups'])
        self.assertEqual('USD_UP_BIAS', first['bias'])
        items += parsed('US inflation was below expectations.', title='US inflation update', link=ARTICLE+'third/')
        result = assess_news(items, NOW)
        self.assertEqual('MIXED', result['bias'])
        self.assertTrue(result['events'][0]['conflicting'])

    def test_opposing_channels_and_risk_are_reported_without_inventing_probability(self):
        result = context('US inflation was above expectations.\nCredit contagion is reducing odds of Fed hikes.')
        self.assertEqual('MIXED', result['bias'])
        self.assertEqual(2, result['event_groups'])
        self.assertEqual(1, result['risk_articles'])
        self.assertFalse(result['accuracy_validated'])
        self.assertNotIn('probability', result)

    def test_missing_news_source_is_explicit_and_not_neutral_evidence(self):
        result = assess_news([], NOW, ['ibkr_news'])
        self.assertEqual('PARTIAL', result['coverage'])
        self.assertEqual('UNCLEAR', result['bias'])
        self.assertEqual(['ibkr_news'], result['unavailable_sources'])

    def test_news_can_only_remove_a_clear_direction_never_boost_base_scores(self):
        outlooks = [{'horizon_reference_observations': 5, 'direction': 'UNCLEAR', 'score': 2},
                    {'horizon_reference_observations': 20, 'direction': 'USD_UP_BIAS', 'score': 3}]
        before = deepcopy(outlooks)
        aligned = combine_outlooks(outlooks, {'bias': 'USD_UP_BIAS'})
        self.assertEqual(['UNCLEAR', 'USD_UP_BIAS'], [r['direction'] for r in aligned])
        for bias in ['MIXED', 'USD_DOWN_BIAS']:
            self.assertEqual(['UNCLEAR', 'UNCLEAR'], [r['direction'] for r in combine_outlooks(outlooks, {'bias': bias})])
        self.assertEqual('USD_UP_BIAS', combine_outlooks(outlooks, {'bias': 'UNCLEAR'})[1]['direction'])
        self.assertEqual(before, outlooks)

    def test_html_and_telegram_use_same_combined_conclusion(self):
        report = demo_report()
        report.update(generated_at=NOW.isoformat(), source_mode='PUBLIC_DATA', status='OK')
        report['news_context'] = context('US inflation was below consensus.')
        report['combined_outlooks'] = combine_outlooks(report['outlooks'], report['news_context'])
        self.assertTrue(any(r['reason']=='NEWS_CONFLICT' for r in report['combined_outlooks']))
        html = cloud_html(report)
        telegram = message(report, now=NOW)
        self.assertIn('Završni zaključak je zato neodređen', html)
        self.assertIn('Mjesec: Nema jasnog smjera', telegram)
        self.assertIn('nisu saglasni', telegram)
        self.assertIn('newsAnalysis.hidden=stale', html)

    def test_news_ui_escapes_untrusted_evidence_and_bad_links(self):
        report = demo_report()
        report['news_context'] = context('US inflation was above consensus.')
        evidence = report['news_context']['events'][0]['evidence'][0]
        evidence.update(reason='<script>bad()</script>', url='javascript:bad()', publisher='<img src=x>')
        html = cloud_html(report)
        self.assertNotIn('<script>bad()', html)
        self.assertNotIn('javascript:bad()', html)
        self.assertIn('&lt;script&gt;bad()', html)


if __name__ == '__main__':
    unittest.main()
