"""Transparent daily USD/EUR analysis. Scores are not calibrated probabilities."""
from __future__ import annotations
import calendar
import csv
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import io
import json
import math
import re
import statistics
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

MODEL_VERSION = "0.1.0"


class DataError(ValueError):
    pass


def finite(value, low=-1000, high=1000):
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise DataError("Invalid numeric observation.")
    return result


def period_date(period):
    if re.fullmatch(r"\d{4}-\d{2}", period):
        year, month = map(int, period.split("-"))
        return date(year, month, calendar.monthrange(year, month)[1])
    return date.fromisoformat(period)


def parse_ecb(body, expected_key, today):
    rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
    found = {}
    for raw in rows:
        if raw.get("KEY") != expected_key:
            raise DataError("ECB returned a different series key.")
        if raw.get("UNIT_MULT") not in ("0", "", None):
            raise DataError("Unexpected ECB unit multiplier.")
        period = raw.get("TIME_PERIOD", "")
        day = period_date(period)
        # A current-month flash estimate may precede month-end. Keep monthly
        # observations only once that month is complete, a conservative cutoff.
        if day > today:
            continue
        if raw.get("OBS_VALUE") in (None, "", ":", "."):
            continue
        value = finite(raw["OBS_VALUE"])
        if period in found and found[period]["value"] != value:
            raise DataError("Conflicting duplicate ECB observations.")
        found[period] = {"date": period, "value": value, "status": raw.get("OBS_STATUS", "")}
    result = sorted(found.values(), key=lambda r: r["date"])
    if not result:
        raise DataError("No usable ECB observations.")
    return result


def parse_effr(body, today):
    data = json.loads(body)
    found = {}
    for row in data.get("refRates", []):
        if row.get("type") != "EFFR":
            raise DataError("Unexpected NY Fed rate type.")
        day = date.fromisoformat(row["effectiveDate"])
        if day > today:
            continue
        value = finite(row["percentRate"], -10, 100)
        if day.isoformat() in found and found[day.isoformat()]["value"] != value:
            raise DataError("Conflicting EFFR dates.")
        found[day.isoformat()] = {"date": day.isoformat(), "value": value,
                                  "status": row.get("revisionIndicator", "")}
    if not found:
        raise DataError("No usable EFFR observations.")
    return sorted(found.values(), key=lambda r: r["date"])


def parse_cpi(body, today):
    data = json.loads(body)
    series = data.get("Results", {}).get("series", [])
    if data.get("status") != "REQUEST_SUCCEEDED" or len(series) != 1 or series[0].get("seriesID") != "CUUR0000SA0":
        raise DataError("BLS CPI request failed or returned a different series.")
    index = {}
    for row in series[0].get("data", []):
        if not re.fullmatch(r"M(0[1-9]|1[0-2])", row.get("period", "")):
            continue  # M13 annual average is not a calendar month.
        year, month = int(row["year"]), int(row["period"][1:])
        period = f"{year:04d}-{month:02d}"
        if period_date(period) > today:
            continue
        if str(row.get("value", "")).strip() in {"", "-", ".", ":"}:
            continue  # BLS uses '-' for unavailable observations; never treat as zero.
        value = finite(row["value"], .001, 100000)
        if period in index and index[period] != value:
            raise DataError("Conflicting CPI observations.")
        index[period] = value
    result = []
    for period, value in sorted(index.items()):
        prior = f"{int(period[:4])-1}{period[4:]}"
        if prior in index:
            result.append({"date": period, "value": (value/index[prior]-1)*100, "status": "CPI-U NSA YoY calculated"})
    if not result:
        raise DataError("CPI has no matching same-month prior-year index.")
    return result


def safe_link(link, hosts):
    url = urlsplit(link)
    return link if url.scheme == "https" and url.hostname in hosts and not url.username and not url.password else ""


def parse_news(body, publisher, now):
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise DataError("Unexpected XML entity declarations.")
    root = ET.fromstring(body)
    output, seen = [], set()
    hosts = {"www.ecb.europa.eu", "www.federalreserve.gov"}
    for item in root.findall(".//item"):
        title = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", "", item.findtext("title", "")))).strip()
        link = safe_link(item.findtext("link", "").strip(), hosts)
        try:
            when = parsedate_to_datetime(item.findtext("pubDate", ""))
            if when.tzinfo is None:
                continue
            when = when.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
        age = (now-when).total_seconds()
        if not title or not link or link in seen or not 0 <= age <= 30*86400:
            continue
        seen.add(link)
        relevant = bool(re.search(r"monetary policy|FOMC|interest rate|inflation|meeting of|discount rate|economic outlook", title, re.I))
        output.append({"publisher": publisher, "title": title[:280], "url": link,
                       "published_at": when.isoformat(), "policy_related_title": relevant,
                       "recent_policy_release": relevant and age <= 48*3600})
    return sorted(output, key=lambda r: r["published_at"], reverse=True)[:8]


def fresh(rows, today, days, label):
    if not rows:
        raise DataError(f"{label}: no usable data.")
    age = (today-period_date(rows[-1]["date"])).days
    if not 0 <= age <= days:
        raise DataError(f"{label}: latest observation {rows[-1]['date']} is stale/future.")


def sign(value, tolerance):
    return 1 if value > tolerance+1e-10 else -1 if value < -tolerance-1e-10 else 0


def rates_context(effr, estr, today):
    fresh(effr, today, 7, "EFFR")
    fresh(estr, today, 7, "ESTR")
    us = {r["date"]: r["value"] for r in effr}
    eu = {r["date"]: r["value"] for r in estr}
    days = sorted(us.keys() & eu.keys())
    if len(days) < 21:
        raise DataError("Need 21 matching US/EUR overnight-rate dates.")
    last, prior = days[-1], days[-21]
    if (today-date.fromisoformat(last)).days > 7:
        raise DataError("Matching rate date is stale.")
    gap = us[last]-eu[last]
    change = gap-(us[prior]-eu[prior])
    return {"date": last, "prior_date": prior, "effr_percent": us[last], "estr_percent": eu[last],
            "spread_pp": gap, "spread_change_20_observations_pp": change,
            "change_vote": sign(change, .10),
            "meaning": "Change in the US-minus-EUR overnight-rate gap, not retail interest or expected FX return."}


def inflation_context(cpi, hicp, today):
    fresh(cpi, today, 100, "US CPI inflation")
    fresh(hicp, today, 100, "Euro-area HICP inflation")
    us = {r["date"]: r for r in cpi}
    eu = {r["date"]: r for r in hicp}
    common = sorted(us.keys() & eu.keys())
    if not common:
        raise DataError("No matching US/EUR inflation month.")
    period = common[-1]
    if (today-period_date(period)).days > 100:
        raise DataError("Matching inflation month is stale.")
    return {"period": period, "us_cpi_yoy_percent": us[period]["value"],
            "euro_hicp_yoy_percent": eu[period]["value"], "hicp_status": eu[period]["status"],
            "latest_us": cpi[-1], "latest_euro": hicp[-1],
            "meaning": "CPI and HICP baskets differ. Context only; no automatic direction vote."}


def analyze(fx, rates, now, source_errors=None):
    source_errors = source_errors or {}
    result = {"model_version": MODEL_VERSION, "mode": "ANALYSIS_ONLY", "pair": "USD/EUR",
              "unit": "EUR per 1 USD", "generated_at": now.isoformat(), "status": "OK",
              "reference_data": True, "source_errors": source_errors, "outlooks": [], "rates": rates,
              "issues": [], "orders_sent": 0}
    try:
        fresh(fx, now.date(), 5, "ECB exchange rate")
        if len(fx) < 60:
            raise DataError("Need 60 daily reference-rate observations.")
        if len({r["date"] for r in fx}) != len(fx) or fx != sorted(fx, key=lambda r: r["date"]):
            raise DataError("Exchange-rate dates must be unique and increasing.")
        if any(not .01 < r["value"] < 100 for r in fx):
            raise DataError("Invalid USD per EUR exchange rate.")
        # ECB quotes USD per EUR; invert EVERY observation before calculating
        # momentum/SMA. A rising displayed line always means stronger USD.
        values = [1/r["value"] for r in fx]
        spot = values[-1]
        mean = lambda n: statistics.mean(values[-n:])
        change = lambda n: (spot/values[-n-1]-1)*100
        recent = values[-61:]
        logs = [math.log(b/a) for a,b in zip(recent[:-1],recent[1:])]
        daily_vol = statistics.stdev(logs)*100
        result.update(reference_date=fx[-1]["date"], eur_per_usd=spot, usd_per_eur=fx[-1]["value"],
                      change_5_observations_percent=change(5), change_20_observations_percent=change(20),
                      daily_volatility_60_observations_percent=daily_vol,
                      annualized_volatility_percent=daily_vol*math.sqrt(252),
                      sma5=mean(5), sma20=mean(20), sma50=mean(50),
                      chart=[{"date": r["date"], "eur_per_usd": v} for r,v in zip(fx[-120:], values[-120:])])
        for horizon in (5,20):
            fast, slow = (5,20) if horizon == 5 else (20,50)
            mom = change(horizon)
            tolerance = max(.10 if horizon == 5 else .25, .5*daily_vol*math.sqrt(horizon))
            trend = (mean(fast)/mean(slow)-1)*100
            location = (spot/mean(slow)-1)*100
            votes = [
                {"factor": f"USD momentum, {horizon} observations", "value": mom, "unit": "%", "threshold": tolerance, "vote": sign(mom,tolerance)},
                {"factor": f"SMA{fast} / SMA{slow}", "value": trend, "unit": "%", "threshold": .05 if horizon==5 else .15, "vote": sign(trend,.05 if horizon==5 else .15)},
                {"factor": f"USD price / SMA{slow}", "value": location, "unit": "%", "threshold": .05 if horizon==5 else .10, "vote": sign(location,.05 if horizon==5 else .10)},
            ]
            technical_score = sum(x["vote"] for x in votes)
            if rates:
                votes.append({"factor": "Change in US-minus-EUR overnight rate gap", "value": rates["spread_change_20_observations_pp"],
                              "unit": "pp", "threshold": .10, "vote": rates["change_vote"]})
            score = sum(x["vote"] for x in votes)
            if not rates:
                direction = "INSUFFICIENT_DATA"
            else:
                direction = "USD_UP_BIAS" if score >= 3 else "USD_DOWN_BIAS" if score <= -3 else "UNCLEAR"
            result["outlooks"].append({"horizon_reference_observations": horizon, "direction": direction,
                                        "score": score, "technical_score": technical_score, "factors": votes,
                                        "probability": None, "price_target": None})
        if not rates:
            result["status"] = "INSUFFICIENT_DATA"
            result["issues"].append("Missing current comparable interest-rate data; no combined directional conclusion.")
        elif source_errors:
            result["status"] = "PARTIAL_CONTEXT"
    except (DataError, ValueError, TypeError, KeyError, ArithmeticError) as exc:
        result["status"] = "INSUFFICIENT_DATA"
        result["issues"].append(str(exc))
        result["outlooks"] = []
    return result


def conversion(amount_usd, eur_per_usd, cost_bps=0, flat_fee_eur=0, usd_move_percent=0):
    amount = finite(amount_usd,0,1e9)
    rate = finite(eur_per_usd,.0001,100)
    bps = finite(cost_bps,0,9999)
    fee = finite(flat_fee_eur,0,1e7)
    move = finite(usd_move_percent,-99,1000)
    gross = amount*rate*(1+move/100)
    return {"gross_eur": gross, "estimated_net_eur": gross*(1-bps/10000)-fee}
