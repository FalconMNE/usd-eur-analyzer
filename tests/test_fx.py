from datetime import date,datetime,timedelta,timezone
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fx_analyzer import demo_report, run_live, run_lock, save
from fx_core import (DataError, analyze, conversion, inflation_context, parse_cpi, sign,
                     parse_ecb, parse_effr, parse_news, rates_context)
from fx_report import render_report

NOW=datetime(2026,10,14,15,0,tzinfo=timezone.utc)


def fx_rows(direction=1):
    days=[NOW.date()-timedelta(days=i+1) for i in range(120)][::-1]
    return [{"date":d.isoformat(),"value":1/(.90+direction*i*.0002),"status":"DEMO"} for i,d in enumerate(days)]


def rates(change=0):
    return {"date":"2026-10-13","prior_date":"2026-09-15","effr_percent":4,"estr_percent":2,
            "spread_pp":2,"spread_change_20_observations_pp":change,"change_vote":1 if change>.1 else -1 if change<-.1 else 0}


class ParserTests(unittest.TestCase):
    def test_ecb_sorts_and_skips_future_or_missing(self):
        body=b'KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT,OBS_STATUS\nEXR.D.USD.EUR.SP00.A,2026-10-13,1.12,0,A\nEXR.D.USD.EUR.SP00.A,2026-10-12,1.11,0,A\nEXR.D.USD.EUR.SP00.A,2026-10-20,1.10,0,A\nEXR.D.USD.EUR.SP00.A,2026-10-11,,0,A\n'
        rows=parse_ecb(body,"EXR.D.USD.EUR.SP00.A",NOW.date())
        self.assertEqual(["2026-10-12","2026-10-13"],[r["date"] for r in rows])

    def test_wrong_series_multiplier_and_conflicting_duplicates_rejected(self):
        for body in [b'KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\nOTHER,2026-10-13,1.12,0\n',
                     b'KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\nFX,2026-10-13,1.12,2\n',
                     b'KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\nFX,2026-10-13,1.12,0\nFX,2026-10-13,1.13,0\n']:
            with self.subTest(body=body),self.assertRaises(DataError):
                parse_ecb(body,"FX",NOW.date())

    def test_nan_is_rejected(self):
        with self.assertRaises(DataError):
            parse_ecb(b'KEY,TIME_PERIOD,OBS_VALUE\nFX,2026-10-13,NaN\n',"FX",NOW.date())

    def test_effr_type_and_dates(self):
        data={"refRates":[{"effectiveDate":"2026-10-13","type":"EFFR","percentRate":3.88},
                          {"effectiveDate":"2026-10-20","type":"EFFR","percentRate":4}]}
        self.assertEqual(1,len(parse_effr(json.dumps(data),NOW.date())))
        data["refRates"][0]["type"]="SOFR"
        with self.assertRaises(DataError):parse_effr(json.dumps(data),NOW.date())

    def test_cpi_uses_exact_prior_year_month_and_ignores_annual_average(self):
        data={"status":"REQUEST_SUCCEEDED","Results":{"series":[{"seriesID":"CUUR0000SA0","data":[
              {"year":"2026","period":"M08","value":"103"},
              {"year":"2025","period":"M08","value":"100"},
              {"year":"2026","period":"M13","value":"200"}]}]}}
        rows=parse_cpi(json.dumps(data),NOW.date())
        self.assertEqual(1,len(rows));self.assertAlmostEqual(3,rows[0]["value"])
        data["Results"]["series"][0]["data"][1]["period"]="M07"
        with self.assertRaises(DataError):parse_cpi(json.dumps(data),NOW.date())

    def test_rss_rejects_external_links_duplicates_and_future_items(self):
        template='<item><title>FOMC policy statement</title><link>{}</link><pubDate>{}</pubDate></item>'
        good=template.format('https://www.federalreserve.gov/newsevents/statement.htm','Tue, 13 Oct 2026 18:00:00 GMT')
        bad=template.format('https://evil.example/a','Tue, 13 Oct 2026 18:00:00 GMT')
        future=template.format('https://www.federalreserve.gov/newsevents/future.htm','Tue, 20 Oct 2026 18:00:00 GMT')
        rows=parse_news(('<rss><channel>'+good+good+bad+future+'</channel></rss>').encode(),'Fed',NOW)
        self.assertEqual(1,len(rows));self.assertTrue(rows[0]["recent_policy_release"])

    def test_bls_missing_observation_is_skipped_without_losing_valid_month(self):
        data={"status":"REQUEST_SUCCEEDED","Results":{"series":[{"seriesID":"CUUR0000SA0","data":[
              {"year":"2026","period":"M09","value":"-"},
              {"year":"2026","period":"M08","value":"103"},
              {"year":"2025","period":"M08","value":"100"}]}]}}
        rows=parse_cpi(json.dumps(data),NOW.date())
        self.assertEqual("2026-08",rows[-1]["date"])
        self.assertAlmostEqual(3,rows[-1]["value"])

    def test_rss_xml_entities_are_rejected(self):
        with self.assertRaises(DataError):parse_news(b'<!DOCTYPE rss [<!ENTITY x "x">]><rss/>','Fed',NOW)


class MacroTests(unittest.TestCase):
    def test_rates_are_aligned_by_same_date_not_list_index(self):
        us=[{"date":(NOW.date()-timedelta(days=i+1)).isoformat(),"value":4} for i in range(40)][::-1]
        eu=[{"date":r["date"],"value":2} for r in us[:-1]]
        out=rates_context(us,eu,NOW.date())
        self.assertEqual("2026-10-12",out["date"])
        self.assertEqual(2,out["spread_pp"])
        self.assertEqual(0,out["change_vote"])  # high static USD rate is not a bullish vote

    def test_widening_rate_gap_has_positive_change(self):
        us=[{"date":(NOW.date()-timedelta(days=i+1)).isoformat(),"value":4} for i in range(40)][::-1]
        eu=[{"date":r["date"],"value":2} for r in us]
        us[-1]["value"]=4.25
        out=rates_context(us,eu,NOW.date())
        self.assertEqual(.25,out["spread_change_20_observations_pp"])
        self.assertEqual(1,out["change_vote"])

    def test_mismatched_inflation_months_use_latest_common(self):
        us=[{"date":"2026-08","value":3.4,"status":"A"}]
        eu=[{"date":"2026-08","value":3.1,"status":"A"},{"date":"2026-09","value":3.8,"status":"E"}]
        out=inflation_context(us,eu,NOW.date())
        self.assertEqual("2026-08",out["period"])
        self.assertEqual(3.1,out["euro_hicp_yoy_percent"])
        self.assertEqual("2026-09",out["latest_euro"]["date"])

    def test_stale_macroeconomics_rejected(self):
        rows=[{"date":"2025-01","value":3,"status":"A"}]
        with self.assertRaises(DataError):inflation_context(rows,rows,NOW.date())


class SignalTests(unittest.TestCase):
    def test_threshold_is_stable_against_float_roundoff(self):
        self.assertEqual(0,sign(.10000000000000009,.1))
        self.assertEqual(0,sign(-.10000000000000009,.1))

    def test_exact_minimum_history_has_correct_nonzero_return_volatility(self):
        rows=fx_rows(1)[-60:]
        rows[-2]["value"]*=1.01
        out=analyze(rows,rates(),NOW)
        self.assertEqual("OK",out["status"])
        self.assertGreater(out["daily_volatility_60_observations_percent"],0)

    def test_usd_strength_direction_uses_inverse_of_ecb_quote(self):
        out=analyze(fx_rows(1),rates(),NOW)
        self.assertEqual("OK",out["status"])
        self.assertTrue(all(r["direction"]=="USD_UP_BIAS" for r in out["outlooks"]))
        self.assertGreater(out["change_5_observations_percent"],0)
        self.assertAlmostEqual(1/fx_rows(1)[-1]["value"],out["eur_per_usd"])

    def test_usd_weakening_direction(self):
        out=analyze(fx_rows(-1),rates(),NOW)
        self.assertTrue(all(r["direction"]=="USD_DOWN_BIAS" for r in out["outlooks"]))

    def test_flat_market_is_unclear(self):
        out=analyze(fx_rows(0),rates(),NOW)
        self.assertTrue(all(r["direction"]=="UNCLEAR" for r in out["outlooks"]))

    def test_inverse_percentage_is_not_just_negative_percentage(self):
        rows=fx_rows(0)
        rows[-1]["value"]*=2
        out=analyze(rows,rates(),NOW)
        self.assertAlmostEqual(-50,out["change_5_observations_percent"])

    def test_conflicting_interest_signal_can_remove_direction(self):
        out=analyze(fx_rows(1),rates(-.25),NOW)
        self.assertTrue(all(r["direction"]=="UNCLEAR" for r in out["outlooks"]))

    def test_missing_rates_never_produces_combined_forecast(self):
        out=analyze(fx_rows(1),None,NOW)
        self.assertEqual("INSUFFICIENT_DATA",out["status"])
        self.assertTrue(all(r["direction"]=="INSUFFICIENT_DATA" for r in out["outlooks"]))

    def test_stale_insufficient_duplicate_or_invalid_fx_blocks(self):
        stale=fx_rows();stale=stale[:-10]
        duplicate=fx_rows();duplicate.append(duplicate[-1])
        invalid=fx_rows();invalid[-1]["value"]=0
        for rows in [stale,fx_rows()[-10:],duplicate,invalid]:
            with self.subTest(rows=len(rows)):
                out=analyze(rows,rates(),NOW)
                self.assertEqual("INSUFFICIENT_DATA",out["status"])
                self.assertEqual([],out["outlooks"])

    def test_missing_optional_context_is_visible_not_a_fake_probability(self):
        out=analyze(fx_rows(),rates(),NOW,{"cpi":"Unavailable"})
        self.assertEqual("PARTIAL_CONTEXT",out["status"])
        self.assertTrue(all(r["probability"] is None for r in out["outlooks"]))


class DeliveryTests(unittest.TestCase):
    def test_conversion_costs_and_scenarios(self):
        out=conversion(1000,.9,50,2,1)
        self.assertAlmostEqual(909,out["gross_eur"])
        self.assertAlmostEqual(902.455,out["estimated_net_eur"])
        with self.assertRaises(DataError):conversion(-1,.9)

    def test_render_escapes_source_text_and_has_no_broker_commands(self):
        out=demo_report();out["issues"]=['<script>alert("bad")</script>']
        html=render_report(out)
        self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('<script>alert("bad")',html)
        self.assertIn('DEMO',html)
        self.assertIn('EUR',html)

    def test_network_failure_replaces_old_forecast(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save(root/'output',demo_report())
            def fail(url):raise OSError('offline')
            report=run_live(root,fail,NOW,lambda *a,**k:None)
            signal=json.loads((root/'output/fx_signal.json').read_text())
            self.assertEqual('INSUFFICIENT_DATA',signal['status'])
            self.assertEqual([],signal['outlooks'])
            self.assertEqual('PUBLIC_DATA',signal['source_mode'])
            self.assertEqual(7,len(report['sources']))

    def test_interrupt_invalidates_prior_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save(root/'output',demo_report())
            def interrupt(url):raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):run_live(root,interrupt,NOW,lambda *a,**k:None)
            self.assertEqual('FAILED',json.loads((root/'output/fx_signal.json').read_text())['status'])

    def test_concurrent_runs_are_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fx.lock'
            with run_lock(path):
                with self.assertRaises(DataError),run_lock(path):pass


if __name__=='__main__':unittest.main()
