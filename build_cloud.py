"""Build the public report on a cloud runner; stdlib only, no broker access."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from fx_analyzer import atomic_text, collect, demo_report, fetch
from fx_report import render_report
from fx_calendar import collect_calendar, fetch_calendar


def cloud_html(report):
    html = render_report(report)
    html = html.replace(
        'Pokreni <b>01_Analiza_USD_EUR.cmd</b> za novu procjenu.',
        'Osvježi stranicu. Ako datum ostane isti, provjeri posljednje pokretanje u GitHub Actions. Ovo nije nova procjena.')
    html = html.replace(
        'Nova analiza se pokreće ručno. Promjena iznosa u kalkulatoru ne osvježava kurs.',
        'Nova analiza nastaje nakon uspješnog pokretanja u oblaku. Raspored mora biti uključen u repozitorijumu. Promjena iznosa u kalkulatoru ne osvježava kurs. Iznos se ne šalje serveru.')
    html = html.replace('</header>', '<p><button type="button" onclick="location.reload()" style="padding:12px 18px;border:1px solid #087c78;border-radius:9px;background:white;color:#087c78;font:inherit;cursor:pointer">Osvježi prikaz</button></p><p class="muted">Dugme učitava posljednji objavljeni izvještaj. Nova analiza se računa na serveru, prema rasporedu. Datum kursa i datum izrade mogu se razlikovati.</p></header>', 1)
    # On old snapshots hide directional cards, while retaining dated historical
    # observations. Check again while the phone tab remains open.
    html = html.replace("update();\n</script>", """update();
function freshness(){
 const stale=!data.demo&&(!Number.isFinite(Date.parse(data.generated))||Date.now()-Date.parse(data.generated)>36*3600*1000);
 document.getElementById('stale').style.display=stale?'block':'none';
 const cards=document.querySelector('.horizons');
 if(cards)cards.style.display=stale?'none':'';
 const newsAnalysis=document.getElementById('news-analysis');
 if(newsAnalysis)newsAnalysis.hidden=stale;
 const calendarNotice=document.getElementById('calendar-stale');
 if(calendarNotice)calendarNotice.hidden=!stale;
}
freshness();setInterval(freshness,60000);
</script>""")
    return html


def build(output, getter=fetch, now=None, demo=False, calendar_getter=fetch_calendar):
    now = now or datetime.now(timezone.utc)
    if demo:
        report = demo_report()
    else:
        try:
            report = collect(now, getter=getter)
        except Exception:
            # Never re-use a successful old report after an unsuccessful refresh.
            report = {"mode":"ANALYSIS_ONLY","source_mode":"PUBLIC_DATA","pair":"USD/EUR",
                      "unit":"EUR per 1 USD","generated_at":now.isoformat(),"status":"FAILED",
                      "issues":["Novi pregled nije završen. Nema važeće procjene smjera."],
                      "outlooks":[],"sources":[],"source_errors":{},"news":[],"rates":None,"inflation":None}
    if demo:
        report['calendar'] = {'status':'DEMO', 'checked_at':now.isoformat(), 'days':30, 'events':[], 'sources':[]}
    else:
        report['calendar'] = collect_calendar(now, getter=calendar_getter)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    atomic_text(output/'index.html', cloud_html(report))
    atomic_text(output/'report.json', json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
    atomic_text(output/'.nojekyll', '')
    print('Built report. Status:', report['status'], '| Source:', report['source_mode'])
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('public'))
    p.add_argument('--demo', action='store_true')
    p.add_argument('--check', action='store_true', help='Validate last run after publishing failure notice if needed')
    args = p.parse_args()
    if args.check:
        report = json.loads((args.output/'report.json').read_text(encoding='utf-8'))
        return 0 if report['status'] in ('OK','PARTIAL_CONTEXT') and report['source_mode']=='PUBLIC_DATA' else 1
    build(args.output, demo=args.demo)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
