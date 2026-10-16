from html import escape
import json
import math
from fx_core import conversion, safe_link
from fx_calendar import calendar_html
from fx_news import NEWS_HOSTS, TOPIC_LABELS

LABELS={"USD_UP_BIAS":"Prednost scenariju jačanja USD", "USD_DOWN_BIAS":"Prednost scenariju slabljenja USD",
        "UNCLEAR":"Nema jasnog smjera", "INSUFFICIENT_DATA":"Nedovoljno podataka"}
STATUS={"OK":"Podaci učitani", "PARTIAL_CONTEXT":"Dio dodatnih podataka nedostaje", "INSUFFICIENT_DATA":"Nedovoljno podataka",
        "UPDATING":"Preuzimanje je u toku", "FAILED":"Analiza nije završena"}


def e(value):return escape(str(value),quote=True)


def num(value,digits=2,suffix=""):
    if value is None:return "—"
    return f"{float(value):,.{digits}f}{suffix}"


def chart_svg(points):
    if not points:return '<p class="muted">Nema dovoljno podataka za grafikon.</p>'
    values=[r["eur_per_usd"] for r in points]
    lo,hi=min(values),max(values)
    pad=max((hi-lo)*.12,.0003);lo-=pad;hi+=pad
    left,right,top,bottom=78,975,20,240
    x=lambda i:left+i*(right-left)/max(1,len(points)-1)
    y=lambda v:bottom-(v-lo)/(hi-lo)*(bottom-top)
    line=" ".join(f"{x(i):.1f},{y(v):.1f}" for i,v in enumerate(values))
    labels=[]
    for j in range(5):
        v=lo+(hi-lo)*j/4;yy=y(v)
        labels.append(f'<line x1="{left}" x2="{right}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="#dae4eb"/><text x="64" y="{yy+4:.1f}" text-anchor="end" fill="#526775" font-size="12">{v:.4f}</text>')
    for i in (0,len(points)//2,len(points)-1):
        anchor="start" if i==0 else "end" if i==len(points)-1 else "middle"
        labels.append(f'<text x="{x(i):.1f}" y="270" text-anchor="{anchor}" fill="#526775" font-size="12">{e(points[i]["date"])}</text>')
    return f'<svg viewBox="0 0 1000 282" role="img" aria-label="Dnevni referentni kurs: EUR za jedan USD. Rast linije znači jačanje dolara." style="width:100%;height:auto">{"".join(labels)}<polyline points="{line}" fill="none" stroke="#087c78" stroke-width="3" stroke-linejoin="round"/><circle cx="{x(len(values)-1):.1f}" cy="{y(values[-1]):.1f}" r="4" fill="#087c78"/></svg>'


def news_context_html(context):
    if not context:
        return ''
    rows=[]
    for event in context.get('events',[]):
        region='SAD' if event['region']=='US' else 'Eurozona'
        influence='Suprotni uticaji' if event.get('conflicting') else 'Moguća podrška USD' if event['usd_direction']>0 else 'Moguć pritisak na USD'
        reasons=list(dict.fromkeys(x['reason'] for x in event.get('evidence',[])))[:2]
        links=[];seen=set()
        for evidence in event.get('evidence',[]):
            url=safe_link(evidence['url'],NEWS_HOSTS)
            if url and url not in seen:
                links.append(f'<a href="{e(url)}" target="_blank" rel="noopener">{e(evidence["publisher"])}</a>')
                seen.add(url)
        rows.append(f'<li><strong>{e(region)} · {e(TOPIC_LABELS.get(event["topic"],event["topic"]))}</strong> — {e(influence)}<p>{e(" ".join(reasons))}</p><small>Izvori: {" · ".join(links[:3])}</small></li>')
    missing='<p class="alert">Dio izvora vijesti nije učitan. Prikazana procjena koristi samo dostupne tekstove.</p>' if context.get('unavailable_sources') else ''
    risk='<p class="alert">Tekstovi pominju i geopolitički ili kreditni rizik. Njegov uticaj na USD može biti dvosmislen i nije mu automatski dodijeljen smjer.</p>' if context.get('risk_articles') else ''
    empty='<p>U dostupnim tekstovima nije prepoznat dovoljno jasan događaj. To ne znači da nema važnih vijesti.</p>' if not rows else ''
    return f'''<section class="panel" id="news-analysis"><span class="eyebrow">Vijesti i procjena smjera</span>
<h2>{e(context['label'])}</h2><p>Posljednja {context['window_hours']} sata · pregledano {context['active_articles']} objava · {context['event_groups']} oblasti sa prepoznatim uticajem.</p>
{missing}{risk}<ul class="news">{''.join(rows)}</ul>{empty}
<p class="muted">Provjerava se dostupni RSS tekst: sadržaj članka, sažetak ili samo naslov, zavisno od izvora. Tekstovi o istoj oblasti su grupisani; broj članaka ne dodaje glasove. Objave centralnih banaka odvojene su od tržišnih komentara.</p>
<p class="muted">Ovo je eksperimentalno tumačenje. Inflacija ili kamate same ne određuju kurs; reakcija zavisi i od očekivanja i već ugrađenih informacija. Suprotni uticaji mogu učiniti završni zaključak neodređenim. Saglasne vijesti ne povećavaju numerički skor niti dokazuju veću tačnost.</p></section>'''


def render_report(report):
    demo=report.get("source_mode")=="DEMO"
    spot=report.get("eur_per_usd")
    horizons=[]
    combined={x['horizon_reference_observations']:x for x in report.get('combined_outlooks',[])}
    for item in report.get("outlooks",[]):
        days=item["horizon_reference_observations"]
        label="Približno jedna sedmica" if days==5 else "Približno jedan mjesec"
        conclusion=combined.get(days,item)
        direction=conclusion["direction"]
        news_note=''
        if conclusion.get('reason')=='NEWS_CONFLICT':
            news_note='<p class="alert">Prepoznati uticaji vijesti nisu saglasni sa osnovnim signalom. Završni zaključak je zato neodređen.</p>'
        elif conclusion.get('reason')=='ALIGNED':
            news_note='<p>Prepoznati uticaji vijesti saglasni su sa osnovnim signalom.</p>'
        cls="up" if direction=="USD_UP_BIAS" else "down" if direction=="USD_DOWN_BIAS" else "neutral"
        factors="".join(f'<tr><td>{e(x["factor"])}</td><td>{num(x["value"],3," "+x["unit"])}</td><td>{x["vote"]:+d}</td></tr>' for x in item["factors"])
        horizons.append(f'''<article class="outlook {cls}"><span class="eyebrow">{label}</span>
<h2>{LABELS[direction]}</h2><p>{days} narednih ECB dnevnih objava, uz praznike.</p>
<div class="score">{item['score']:+d}<small>osnovni skor kursa i kamata, raspon −4 do +4</small></div>{news_note}
<details><summary>Zašto je dobijen ovaj rezultat?</summary><table><thead><tr><th>Pokazatelj</th><th>Vrijednost</th><th>Glas</th></tr></thead><tbody>{factors}</tbody></table>
<p>+1 podržava jačanje USD, −1 slabljenje, 0 bez izraženog signala. Osnovni zbir najmanje +3 daje prednost jačanju; najviše −3 slabljenju. Ostalo je neodređeno. Tehnički pokazatelji su međusobno povezani. Provjera vijesti može ublažiti jasan zaključak u neodređen, bez mijenjanja ovog skora.</p></details></article>''')
    if not horizons:horizons=['<article class="outlook neutral"><h2>Trenutno nema procjene smjera</h2><p>Provjeri podatke i ponovi analizu.</p></article>']
    rates=report.get("rates") or {}
    inflation=report.get("inflation") or {}
    source_rows=[]
    for source in report.get("sources",[]):
        url=safe_link(source["url"],{"data-api.ecb.europa.eu","markets.newyorkfed.org","api.bls.gov"}|NEWS_HOSTS)
        link=f'<a href="{e(url)}" target="_blank" rel="noopener">{e(source["name"])}</a>' if url else e(source["name"])
        source_rows.append(f'<tr><td>{link}</td><td>{e(source["status"])}</td><td>{e(source.get("latest_observation") or "RSS / vidi datum objave")}</td><td>{source["observations"]}</td></tr>')
    news=[]
    for item in report.get("news",[])[:20]:
        link=safe_link(item["url"],NEWS_HOSTS)
        title=f'<a href="{e(link)}" target="_blank" rel="noopener">{e(item["title"])}</a>' if link else e(item["title"])
        marker=' <span class="pill">novija objava o politici</span>' if item["recent_policy_release"] else ""
        kind='Tržišni komentar' if item.get('source_kind')=='COMMENTARY' else 'Zvanična objava'
        author=' · '+e(item['author']) if item.get('author') else ''
        news.append(f'<li>{title}{marker}<small>{e(item["publisher"])}{author} · {kind} · <time data-local-time="{e(item["published_at"])}">{e(item["published_at"])}</time></small></li>')
    issues=list(report.get("issues",[]))+[f"{key}: {value}" for key,value in report.get("source_errors",{}).items()]
    problem_html='<ul>'+''.join(f'<li>{e(x)}</li>' for x in issues)+'</ul>' if issues else ''
    scenarios=""
    if spot:
        for move in (-3,-1,0,1,3):
            amount=conversion(1000,spot,usd_move_percent=move)["gross_eur"]
            scenarios+=f'<tr><td>{move:+d}%</td><td data-scenario="{move}">{num(amount,2," EUR")}</td></tr>'
    calc=f'''<div class="fields"><label>Iznos u USD<input id="amount" type="number" min="0" max="1000000000" step="100" value="1000"></label>
<label>Ukupan trošak u %<input id="cost" type="number" min="0" max="99" step="0.01" value="0"></label>
<label>Fiksna naknada u EUR<input id="fee" type="number" min="0" max="10000000" step="0.01" value="0"></label></div>
<p>Po referentnom kursu, poslije unesenih procijenjenih troškova: <strong id="converted">{num(conversion(1000,spot)['gross_eur'],2,' EUR') if spot else '—'}</strong></p>
<p id="calc-error" role="status"></p><table><thead><tr><th>Promjena vrijednosti USD u EUR</th><th>Procijenjeni iznos poslije troškova</th></tr></thead><tbody>{scenarios}</tbody></table>
<p class="muted">Ovo su scenariji, ne prognoze. Početnih 0% troška nije provjerena ponuda banke/brokera. U procenat unesi ukupnu procjenu spreada i proporcionalnih naknada za jednu konverziju USD → EUR; fiksnu naknadu unesi posebno.</p>'''
    policy='<p class="alert">Pronađeno je novije saopštenje povezano s monetarnom politikom. Otvori izvor i provjeri kontekst; pravila prepoznaju samo dio izraza iz dostupnog RSS teksta i ne provjeravaju nezavisno tržišni konsenzus.</p>' if report.get("recent_policy_release") else ''
    config=json.dumps({"rate":spot,"generated":report["generated_at"],"demo":demo},allow_nan=False)
    return f'''<!doctype html><html lang="sr-Latn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>USD / EUR — procjena smjera</title><style>
:root{{--ink:#17303c;--muted:#526775;--teal:#087c78;--line:#d8e3e8;--bg:#f3f6f7}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,Arial,sans-serif}}
main{{max-width:1160px;padding:40px 28px 65px;margin:auto}}.eyebrow{{font-size:12px;font-weight:750;letter-spacing:1.4px;text-transform:uppercase;color:var(--teal)}}h1{{font-size:44px;line-height:1.12;letter-spacing:-1.4px;margin:12px 0 18px}}h2{{font-size:23px;line-height:1.3;margin:10px 0 15px}}h3{{font-size:18px;margin:0 0 16px}}p{{margin:12px 0}}.lead{{max-width:870px;font-size:18px}}.muted,small{{color:var(--muted)}}a{{color:#076966}}header{{margin-bottom:30px}}
.status{{background:#e4eeef;border:1px solid #c2d6d7;border-radius:10px;padding:14px 18px;margin:18px 0}}#stale{{display:none;background:#fff0d4;border:1px solid #dfb55f;padding:15px;border-radius:10px;margin:18px 0}}.topmetrics{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;margin:22px 0}}
.box,.panel,.outlook{{background:#fff;border:1px solid var(--line);border-radius:16px;padding:24px}}.box small{{display:block;font-size:13px}}.box strong{{display:block;font-size:32px;letter-spacing:-1px}}.box.primary{{background:#153c48;color:white;border-color:#153c48}}.box.primary small{{color:#bcd4dc}}.box.primary strong{{font-size:40px}}
.horizons{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}}.outlook{{border-top-width:5px}}.up{{border-top-color:#087c78}}.down{{border-top-color:#b45349}}.neutral{{border-top-color:#ad985f}}.score{{font-size:30px;font-weight:750}}.score small{{display:block;font-size:12px;font-weight:400}}.outlook p{{font-size:14px}}.outlook h2{{min-height:60px}}
.panel{{margin:22px 0}}.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.stats{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.stats strong{{display:block;font-size:26px}}.stats small{{font-size:12px}}.alert{{background:#fff2d9;padding:12px 16px;border-radius:10px}}.pill{{font-size:11px;background:#fff1d1;padding:2px 7px;border-radius:10px;white-space:nowrap}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:10px 8px;text-align:left;border-bottom:1px solid var(--line)}}th{{font-size:12px;color:var(--muted)}}details{{border-top:1px solid var(--line);margin-top:18px;padding-top:14px}}summary{{cursor:pointer;color:#086f6d;font-size:14px;font-weight:650}}.scroll{{overflow-x:auto}}.news{{padding-left:22px}}.news li{{padding:10px 0}}.news small{{display:block;font-size:12px}}
.fields{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}label{{font-size:13px;font-weight:650}}input{{display:block;width:100%;border:1px solid #9bb6c2;border-radius:8px;padding:10px;font:inherit;font-size:18px;background:white;color:var(--ink);margin-top:6px}}input:focus{{outline:2px solid #50b5ac;outline-offset:2px}}#converted{{font-size:26px;color:var(--teal)}}#calc-error{{color:#8d3129}}footer{{font-size:13px;color:var(--muted);margin-top:25px}}
@media(max-width:760px){{main{{padding:26px 15px}}h1{{font-size:34px}}.topmetrics{{grid-template-columns:1fr 1fr}}.box.primary{{grid-column:1/-1}}.horizons,.twocol{{grid-template-columns:1fr}}.panel,.box,.outlook{{padding:19px}}.fields{{grid-template-columns:1fr}}.outlook h2{{min-height:0}}.box strong{{font-size:28px}}.lead{{font-size:16px}}}}
.calendar-list{{list-style:none;padding:0;margin:18px 0}}.calendar-event{{display:grid;grid-template-columns:190px 1fr;gap:16px;padding:16px 0;border-bottom:1px solid var(--line)}}.calendar-event small{{display:block;font-size:12px;overflow-wrap:anywhere}}.calendar-event a{{font-weight:650}}.event-date{{font-size:14px;font-weight:650}}.event-date small{{font-weight:400}}.reference-note{{font-size:14px;color:var(--muted);margin-top:-6px}}time{{overflow-wrap:anywhere}}[hidden]{{display:none!important}}
@media(max-width:520px){{.calendar-event{{grid-template-columns:1fr;gap:5px}}}}
</style></head><body><main><header><span class="eyebrow">{'DEMO · SVI PODACI SU IZMIŠLJENI' if demo else 'Dnevni pregled · javni podaci i tržišni komentari'}</span>
<h1>Da li USD jača prema EUR?</h1><p class="lead">Trend kursa i kamate daju osnovni signal. Provjera događaja u javnim vijestima pokazuje da li postoje saglasni ili suprotni uticaji.</p>
<div class="status"><strong>{e(STATUS.get(report.get('status'),report.get('status')))}</strong> · izvještaj napravljen <time data-local-time="{e(report['generated_at'])}">{e(report['generated_at'])}</time>
<br><small>Heuristička procjena. Zbir signala nije vjerovatnoća, a model nema potvrđenu prognostičku tačnost.</small>{problem_html}</div><div id="stale">Ovaj izvještaj je stariji od 36 sati. Pokreni <b>01_Analiza_USD_EUR.cmd</b> za novu procjenu.</div></header>
<div class="topmetrics"><div class="box primary"><small>1 USD vrijedi — dnevna ECB referenca</small><strong>{num(spot,5,' EUR')}</strong><small>Datum kursa: {e(report.get('reference_date','—'))} · 1 EUR = {num(report.get('usd_per_eur'),4,' USD')}</small><small>Dnevni presjek · nije kurs uživo</small></div>
<div class="box"><small>Promjena USD kroz 5 objava</small><strong>{num(report.get('change_5_observations_percent'),2,'%')}</strong><small>Ostvarena promjena, ne prognoza</small></div>
<div class="box"><small>Promjena USD kroz 20 objava</small><strong>{num(report.get('change_20_observations_percent'),2,'%')}</strong><small>Ostvarena promjena, ne prognoza</small></div></div>
<p class="reference-note">Vrijeme izrade izvještaja i datum kursa nisu isto. Za konverziju koristi konačnu Wise ponudu sa naknadom; Wise i TradingView nisu povezani sa ovim prikazom.</p>
<div class="horizons">{''.join(horizons)}</div>{policy}
{news_context_html(report.get('news_context'))}
{calendar_html(report.get('calendar'))}
<section class="panel"><h2>Kretanje dolara izraženo u eurima</h2><p class="muted">Rast linije = jači USD: za isti broj dolara dobijaš više eura. ECB izvor daje EUR/USD; ovdje je svaka vrijednost pravilno obrnuta.</p>{chart_svg(report.get('chart',[]))}<p class="muted">Dnevne referentne vrijednosti nisu žive bid/ask ponude. Ovaj alat služi za dnevnu analizu i planiranje konverzije.</p></section>
<div class="twocol"><section class="panel"><h3>Kamatni kontekst — uporedivi datum</h3><div class="stats"><div><small>SAD · efektivna stopa EFFR</small><strong>{num(rates.get('effr_percent'),3,'%')}</strong></div><div><small>Eurozona · stopa €STR</small><strong>{num(rates.get('estr_percent'),3,'%')}</strong></div></div>
<p>Datum: {e(rates.get('date','—'))}. Razlika SAD − eurozona: <b>{num(rates.get('spread_pp'),3,' p.p.')}</b>.</p><p>Promjena razlike kroz 20 zajedničkih objava: <b>{num(rates.get('spread_change_20_observations_pp'),3,' p.p.')}</b>.</p>
<p class="muted">Veća postojeća stopa sama ne znači da USD mora rasti. U zbir ulazi samo promjena razlike; ni taj odnos nije pouzdana prognoza. Ovo nisu tvoje kamate u banci/brokeru.</p></section>
<section class="panel"><h3>Inflacija — isti referentni mjesec</h3><div class="stats"><div><small>SAD · CPI-U, godišnja promjena</small><strong>{num(inflation.get('us_cpi_yoy_percent'),2,'%')}</strong></div><div><small>Eurozona · HICP, godišnja promjena</small><strong>{num(inflation.get('euro_hicp_yoy_percent'),2,'%')}</strong></div></div>
<p>Upoređeni mjesec: <b>{e(inflation.get('period','—'))}</b>. HICP oznaka izvora: {e(inflation.get('hicp_status','—'))}.</p>
<p>Posljednji pojedinačni podaci: SAD {e(inflation.get('latest_us',{}).get('date','—'))}; eurozona {e(inflation.get('latest_euro',{}).get('date','—'))}.</p>
<p class="muted">CPI i HICP koriste različite potrošačke korpe. Podaci su kontekst; ne dodjeljuje se automatski pozitivan ili negativan glas valuti zbog veće inflacije.</p></section></div>
<section class="panel"><h2>Šta promjena znači za tvoj iznos?</h2>{calc}</section>
<section class="panel"><h2>Objave centralnih banaka i IBKR komentari</h2><p class="muted">Odabrane objave iz javnih RSS izvora, posljednjih 30 dana. Provjera uticaja koristi samo posljednja 72 sata. Puni članci ostaju na izvornim stranicama.</p><ul class="news">{''.join(news) or '<li>Nema dostupnih novijih objava u ovom snimku.</li>'}</ul></section>
<section class="panel"><details><summary>Izvori i način računanja</summary><div class="scroll"><table><thead><tr><th>Izvor</th><th>Status preuzimanja</th><th>Posljednji period</th><th>Broj podataka</th></tr></thead><tbody>{''.join(source_rows)}</tbody></table></div>
<p>ECB EXR: dnevni USD za 1 EUR, obrnuto u EUR za 1 USD. EFFR i €STR: noćne kamatne stope u procentima, poređene samo na istim datumima. BLS: godišnja CPI promjena iz istog mjeseca prethodne godine. Eurozona: nova HICP serija, uvedena 2026.</p>
<p>Svaki horizont ima 3 tehnička glasa i 1 glas za promjenu kamatne razlike. Slabe promjene unutar praga nose nulu. Vijesti se ne sabiraju sa tim glasovima: provjerava se saglasnost eksplicitno prepoznatih događaja sa osnovnim smjerom. Njihov uticaj na sedmicu i mjesec nije statistički kalibrisan. Parametri nisu potvrđeni kao profitabilna strategija.</p>
<p>Podaci su dnevni/mjesečni, a objave mogu promijeniti sliku. Nema tržišnog konsenzusa, terminskih kamatnih očekivanja, pune analize geopolitičkih vijesti ili kalendara svih budućih događaja.</p></details></section>
<footer>USD/EUR Analyzer Cloud 0.4.0 · ANALYSIS_ONLY · Nema veze sa brokerskim računom i nema slanja naloga. Nova analiza se pokreće ručno. Promjena iznosa u kalkulatoru ne osvježava kurs.</footer>
</main><script>
const data={config};
try{{
 const zone=Intl.DateTimeFormat().resolvedOptions().timeZone;
 const format=new Intl.DateTimeFormat('sr-Latn',{{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short',hour12:false}});
 document.querySelectorAll('[data-local-time]').forEach(el=>{{const value=new Date(el.dataset.localTime);if(Number.isFinite(value.getTime())){{el.textContent=format.format(value);el.title=el.dataset.localTime;}}}});
 const note=document.getElementById('calendar-zone');
 if(note)note.textContent='Poznate satnice: vrijeme tvog uređaja ('+zone+'). Datum bez satnice ostaje datum zvaničnog izvora.';
}}catch(error){{/* UTC text remains available when localization is unsupported. */}}
function convert(amount,rate,costPercent,fee,move=0){{return amount*rate*(1+move/100)*(1-costPercent/100)-fee;}}
function update(){{
 const amount=Number(document.getElementById('amount').value),cost=Number(document.getElementById('cost').value),fee=Number(document.getElementById('fee').value);
 const valid=[amount,cost,fee].every(Number.isFinite)&&amount>=0&&amount<=1e9&&cost>=0&&cost<=99&&fee>=0&&fee<=1e7&&data.rate>0;
 const fmt=v=>v.toLocaleString('de-DE',{{minimumFractionDigits:2,maximumFractionDigits:2}})+' EUR';
 document.getElementById('calc-error').textContent=valid?'':'Unesi važeće brojeve; potreban je i dostupan kurs.';
 document.getElementById('converted').textContent=valid?fmt(convert(amount,data.rate,cost,fee)):'—';
 document.querySelectorAll('[data-scenario]').forEach(el=>{{el.textContent=valid?fmt(convert(amount,data.rate,cost,fee,Number(el.dataset.scenario))):'—';}});
}}
['amount','cost','fee'].forEach(id=>document.getElementById(id).addEventListener('input',update));
if(!data.demo&&(Date.now()-Date.parse(data.generated)>36*3600*1000))document.getElementById('stale').style.display='block';
update();
</script></body></html>'''
