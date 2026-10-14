"""Standalone daily USD/EUR research. Python standard library only; no broker API."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import webbrowser

from fx_core import (DataError, analyze, inflation_context, parse_cpi, parse_ecb,
                     parse_effr, parse_news, rates_context)
from fx_report import render_report

ROOT = Path(__file__).resolve().parent
ENDPOINTS = {
    "fx": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?lastNObservations=320&format=csvdata",
    "effr": "https://markets.newyorkfed.org/api/rates/unsecured/effr/last/80.json",
    "estr": "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?lastNObservations=80&format=csvdata",
    "hicp": "https://data-api.ecb.europa.eu/service/data/HICP/M.U2.N.000000.4D0.ANR?lastNObservations=18&format=csvdata",
    "cpi": "https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0",
    "fed_news": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "ecb_news": "https://www.ecb.europa.eu/rss/press.html",
}
ALLOWED_HOSTS = {urlsplit(url).hostname for url in ENDPOINTS.values()}


def utcnow():
    return datetime.now(timezone.utc)


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".fx-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def write_json(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


@contextmanager
def run_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0"); handle.flush()
        handle.seek(0)
        locked = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            yield
        except OSError as exc:
            raise DataError("Another analysis may be running, or the folder is not writable.") from exc
        finally:
            if locked:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class TrustedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urlsplit(newurl)
        if url.scheme != "https" or url.hostname not in ALLOWED_HOSTS or url.username or url.password:
            raise DataError("Unexpected data-source redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise DataError("Unexpected data-source URL.")
    opener = build_opener(TrustedRedirect)
    for attempt in range(2):
        try:
            req = Request(url, headers={"User-Agent": "USD-EUR-Research/0.1 (public economic data)", "Accept-Encoding": "identity"})
            with opener.open(req, timeout=20) as response:
                body = response.read(4_000_001)
                if len(body) > 4_000_000:
                    raise DataError("Data response exceeds size limit.")
                return body
        except HTTPError as exc:
            if attempt == 0 and exc.code in {429,500,502,503,504}:
                time.sleep(1)
                continue
            raise DataError(f"HTTP {exc.code}; source unavailable.") from exc
    raise DataError("Source unavailable.")


def collect(now, getter=fetch, progress=print):
    parsed, errors, sources = {}, {}, []
    parsers = {
        "fx": lambda b: parse_ecb(b,"EXR.D.USD.EUR.SP00.A",now.date()),
        "effr": lambda b: parse_effr(b,now.date()),
        "estr": lambda b: parse_ecb(b,"EST.B.EU000A2X2A25.WT",now.date()),
        "hicp": lambda b: parse_ecb(b,"HICP.M.U2.N.000000.4D0.ANR",now.date()),
        "cpi": lambda b: parse_cpi(b,now.date()),
        "fed_news": lambda b: parse_news(b,"Federal Reserve",now),
        "ecb_news": lambda b: parse_news(b,"ECB",now),
    }
    for key, url in ENDPOINTS.items():
        if key == "cpi":
            url += f"?startyear={now.year-2}&endyear={now.year}"
        progress(f"Reading {key} ...", flush=True)
        status, rows = "OK", []
        try:
            rows = parsers[key](getter(url))
            parsed[key] = rows
        except (Exception,) as exc:
            # Missing optional sources remain explicit. Missing FX/rates block
            # the combined conclusion; nothing is substituted or fabricated.
            status = "UNAVAILABLE"
            errors[key] = f"{type(exc).__name__}: {exc}"
            progress(f"  {key}: {errors[key]}", flush=True)
        sources.append({"name": key, "url": url, "retrieved_at": utcnow().isoformat(),
                        "status": status, "observations": len(rows),
                        "latest_observation": rows[-1].get("date") if rows and "date" in rows[-1] else None})
    rates, inflation = None, None
    try:
        rates = rates_context(parsed.get("effr",[]),parsed.get("estr",[]),now.date())
    except (DataError,ValueError,KeyError) as exc:
        errors["rates"] = str(exc)
    try:
        inflation = inflation_context(parsed.get("cpi",[]),parsed.get("hicp",[]),now.date())
    except (DataError,ValueError,KeyError) as exc:
        errors["inflation"] = str(exc)
    report = analyze(parsed.get("fx",[]), rates, now, errors)
    report.update(source_mode="PUBLIC_DATA", inflation=inflation, sources=sources,
                  news=sorted(parsed.get("fed_news",[])+parsed.get("ecb_news",[]),key=lambda r:r["published_at"],reverse=True))
    report["recent_policy_release"] = any(x["recent_policy_release"] for x in report["news"])
    return report


def demo_report():
    now = datetime(2026,10,14,15,0,tzinfo=timezone.utc)
    days, day = [], now.date()-timedelta(days=1)
    while len(days)<120:
        if day.weekday()<5: days.append(day)
        day-=timedelta(days=1)
    days.reverse()
    fx=[{"date":d.isoformat(),"value":1/(.86+i*.0003),"status":"DEMO"} for i,d in enumerate(days)]
    us=[{"date":d.isoformat(),"value":3.75,"status":"DEMO"} for d in days[-50:]]
    eu=[{"date":d.isoformat(),"value":2.00,"status":"DEMO"} for d in days[-50:]]
    report=analyze(fx,rates_context(us,eu,now.date()),now)
    report.update(source_mode="DEMO",inflation=None,news=[],sources=[],recent_policy_release=False)
    return report


def save(output, report):
    write_json(output/"report.json",report)
    atomic_text(output/"report.html",render_report(report))
    # Explicit analysis-only schema, not an order ticket or stock-bot candidate.
    write_json(output/"fx_signal.json",{k:report.get(k) for k in
               ("mode","pair","unit","generated_at","reference_date","status","source_mode","model_version","outlooks")})


def run_live(root, getter=fetch, now=None, progress=print):
    output=root/"output"
    with run_lock(root/"fx.lock"):
        pending={"mode":"ANALYSIS_ONLY","pair":"USD/EUR","unit":"EUR per 1 USD","source_mode":"PUBLIC_DATA",
                 "status":"UPDATING","generated_at":utcnow().isoformat(),"outlooks":[],"issues":["A new scan is in progress."],
                 "source_errors":{},"news":[],"sources":[],"rates":None,"inflation":None}
        save(output,pending)  # invalidate all previous outputs before any network call
        try:
            report=collect(now or utcnow(),getter,progress)
            save(output,report)
            return report
        except BaseException:
            pending.update(status="FAILED",issues=["Analysis stopped before completion. No current conclusion is available."])
            save(output,pending)
            raise


def main(argv=None):
    parser=argparse.ArgumentParser(description="Independent USD/EUR daily direction research. No broker connection.")
    parser.add_argument("command",choices=["run","demo","open"])
    parser.add_argument("--open",action="store_true")
    args=parser.parse_args(argv)
    try:
        if args.command=="demo":
            output=ROOT/"demo_output"
            save(output,demo_report())
            print("DEMO ONLY - fictional inputs.")
        elif args.command=="run":
            output=ROOT/"output"
            report=run_live(ROOT)
            print("Status:",report["status"])
            for row in report["outlooks"]:
                print(f"{row['horizon_reference_observations']} observations: {row['direction']}; score {row['score']}")
        else:
            output=ROOT/"output"
            if not (output/"report.html").exists():
                raise DataError("No report yet. Run 01_Analiza_USD_EUR.cmd first.")
        print("Report:",output/"report.html")
        if args.open or args.command=="open": webbrowser.open((output/"report.html").as_uri())
        return 0
    except KeyboardInterrupt:
        print("Stopped. No current signal; no orders.")
        return 130
    except (Exception,) as exc:
        print("ERROR:",str(exc))
        print("Send a screenshot of this message. This program cannot trade.")
        return 2


if __name__=="__main__":
    sys.exit(main())
