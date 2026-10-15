"""Selected official economic calendars. Standard library; no trading signals."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html import escape, unescape
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

SOURCES = {
    'BLS': {
        'feed': 'https://www.bls.gov/schedule/news_release/bls.ics',
        'page': 'https://www.bls.gov/schedule/news_release/',
        'zone': 'America/New_York', 'format': 'ics'},
    'BEA': {
        'feed': 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics',
        'page': 'https://www.bea.gov/news/schedule/',
        'zone': 'America/New_York', 'format': 'ics'},
    'Eurostat': {
        'feed': 'https://ec.europa.eu/eurostat/o/calendars/eventsIcal?theme=0&category=2',
        'page': 'https://ec.europa.eu/eurostat/web/main/news/euro-indicators/release-calendar',
        'zone': 'Europe/Luxembourg', 'format': 'ics'},
    'Fed': {
        'feed': 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',
        'page': 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm',
        'zone': 'America/New_York', 'format': 'fed'},
    'ECB': {
        'feed': 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html',
        'page': 'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html',
        'zone': 'Europe/Berlin', 'format': 'ecb'},
}
HOSTS = {urlsplit(v['feed']).hostname for v in SOURCES.values()}
LABELS = {
    'OK': 'Učitano', 'PARTIAL': 'Dio kalendara nedostaje',
    'UNAVAILABLE': 'Kalendar nije dostupan', 'OUTDATED': 'Raspored nema budućih datuma',
    'DEMO': 'Izmišljeni primjer',
}


class CalendarError(ValueError):
    pass


def safe_url(url):
    p = urlsplit(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and not p.password and p.port in (None, 443)


class CalendarRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not safe_url(newurl):
            raise CalendarError('Unexpected calendar redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_calendar(url):
    if not safe_url(url):
        raise CalendarError('Unexpected calendar source')
    request = Request(url, headers={'User-Agent': 'USD-EUR-Research/0.3 (public economic calendar)',
                                    'Accept-Language': 'en', 'Accept-Encoding': 'identity'})
    with build_opener(CalendarRedirect()).open(request, timeout=20) as response:
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise CalendarError('Calendar response too large')
    return body


def clean(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', ' ', value)).split())


def ical_text(value):
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1].lower() == 'n' else m[1], value)


def topic(source, title):
    title = title.casefold().strip()
    if source == 'BLS':
        return {
            'employment situation': 'SAD — zaposlenost i nezaposlenost',
            'consumer price index': 'SAD — inflacija CPI',
            'producer price index': 'SAD — proizvođačke cijene PPI',
            'job openings and labor turnover survey': 'SAD — slobodna radna mjesta JOLTS',
            'employment cost index': 'SAD — troškovi rada',
        }.get(title)
    if source == 'BEA':
        if title.startswith('personal income and outlays'):
            return 'SAD — potrošnja, prihodi i inflacija PCE'
        if re.match(r'^(gdp\b|gross domestic product\s*[,\(])', title) and 'by county' not in title:
            return 'SAD — BDP'
    if source == 'Eurostat':
        if 'inflation' in title or 'hicp' in title:
            return 'Eurozona — inflacija HICP'
        if 'gdp' in title:
            return 'EU / eurozona — BDP i, kada je uključena, zaposlenost'
        if title == 'unemployment':
            return 'EU / eurozona — nezaposlenost'
    return None


def parse_start(value, params):
    if params.get('VALUE') == 'DATE' or re.fullmatch(r'\d{8}', value):
        return {'date': datetime.strptime(value, '%Y%m%d').date().isoformat(), 'at_utc': None}
    if value.endswith('Z'):
        stamp = datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    else:
        name = params.get('TZID', '').strip('"')
        name = {'US-Eastern': 'America/New_York', 'US/Eastern': 'America/New_York'}.get(name, name)
        if name not in {'America/New_York', 'Europe/Luxembourg', 'Europe/Berlin', 'UTC'}:
            raise CalendarError('Missing or unsupported time zone')
        local = datetime.strptime(value, '%Y%m%dT%H%M%S')
        zone = ZoneInfo(name)
        stamp = local.replace(tzinfo=zone)
        if stamp.utcoffset() != local.replace(tzinfo=zone, fold=1).utcoffset():
            raise CalendarError('Ambiguous or nonexistent local time')
    return {'date': stamp.date().isoformat(), 'at_utc': stamp.astimezone(timezone.utc).isoformat()}


def event(source, title, timing, label=None):
    return {**timing, 'source': source, 'title': title[:350],
            'label': label or topic(source, title), 'url': SOURCES[source]['page'],
            'source_zone': SOURCES[source]['zone']}


def parse_ics(body, source):
    text = re.sub(r'\n[ \t]', '', body.decode('utf-8-sig').replace('\r\n', '\n'))
    if not text.startswith('BEGIN:VCALENDAR') or 'END:VCALENDAR' not in text:
        raise CalendarError('Not a complete iCalendar response')
    blocks = re.findall(r'BEGIN:VEVENT\n(.*?)\nEND:VEVENT', text, re.S)
    if not blocks or len(blocks) != text.count('BEGIN:VEVENT'):
        raise CalendarError('Incomplete or empty calendar')
    versions = {}
    for index, block in enumerate(blocks):
        props = {}
        for line in block.splitlines():
            if ':' not in line:
                continue
            key, value = line.split(':', 1)
            name, *rawparams = key.split(';')
            params = dict(p.split('=', 1) for p in rawparams if '=' in p)
            props[name] = (value, params)
        uid = props.get('UID', (str(index), {}))[0]
        rank = (int(props.get('SEQUENCE', ('0', {}))[0]),
                props.get('LAST-MODIFIED', props.get('DTSTAMP', ('', {})))[0], index)
        if uid not in versions or rank > versions[uid][0]:
            versions[uid] = (rank, props)
    events, skipped = [], 0
    for _, props in versions.values():
        if props.get('STATUS', ('', {}))[0] == 'CANCELLED':
            continue
        title = ical_text(props.get('SUMMARY', ('', {}))[0])
        if not topic(source, title):
            continue
        try:
            if any(key in props for key in ('RRULE', 'RECURRENCE-ID', 'EXDATE', 'RDATE')):
                raise CalendarError('Recurring events are not supported')
            timing = parse_start(*props['DTSTART'])
            events.append(event(source, title, timing))
        except (ValueError, KeyError):
            skipped += 1
    if not events:
        raise CalendarError('No recognizable selected events')
    return events, skipped


def parse_fed(body, now):
    text = body.decode('utf-8')
    headings = list(re.finditer(r'<h4\b[^>]*>\s*(?:<a\b[^>]*>)?(20\d\d) FOMC Meetings', text, re.I))
    months = {name.lower(): i for i, name in enumerate(
        ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'), 1)}
    months.update({key[:3]: value for key, value in list(months.items())})
    events, skipped = [], 0
    for i, head in enumerate(headings):
        year = int(head[1])
        if year not in (now.year, now.year + 1):
            continue
        section = text[head.end():headings[i+1].start() if i+1 < len(headings) else len(text)]
        pairs = re.findall(r'class="[^"]*fomc-meeting__month[^"\n]*"[^>]*>(.*?)</div>\s*<div\b[^>]*class="[^"]*fomc-meeting__date[^"]*"[^>]*>(.*?)</div>', section, re.S)
        for month, days in pairs:
            try:
                month = clean(month).split('/')[-1].strip().lower()
                days = clean(days)
                if not re.fullmatch(r'\d{1,2}(?:\s*[-–]\s*\d{1,2})?\*?', days):
                    raise CalendarError('Unsupported meeting date')
                last = int(re.findall(r'\d+', days)[-1])
                day = date(year, months[month], last).isoformat()
                events.append(event('Fed', f'FOMC: {clean(month)} {days}, {year}',
                                    {'date': day, 'at_utc': None}, 'Fed — završni dan sastanka FOMC'))
            except (ValueError, KeyError):
                skipped += 1
    if not events:
        raise CalendarError('FOMC calendar structure not recognized')
    return events, skipped


def parse_ecb(body):
    pairs = re.findall(r'<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>', body.decode('utf-8'), re.S)
    events, skipped = [], 0
    for day, title in pairs:
        title = clean(title)
        if 'monetary policy meeting' not in title.lower() or 'non-monetary' in title.lower() or '(Day 2)' not in title:
            continue
        try:
            timing = {'date': datetime.strptime(clean(day), '%d/%m/%Y').date().isoformat(), 'at_utc': None}
            events.append(event('ECB', title, timing, 'ECB — završni dan sastanka o monetarnoj politici'))
        except ValueError:
            skipped += 1
    if not events:
        raise CalendarError('ECB calendar structure not recognized')
    return events, skipped


def collect_calendar(now, getter=fetch_calendar, days=30):
    if now.tzinfo is None or not 1 <= days <= 90:
        raise ValueError('An aware timestamp and a 1–90 day window are required')
    now = now.astimezone(timezone.utc)
    end = now + timedelta(days=days)

    def read(source):
        spec = SOURCES[source]
        meta = {'source': source, 'url': spec['page'], 'feed_url': spec['feed'],
                'retrieved_at': now.isoformat(), 'status': 'UNAVAILABLE', 'events': 0}
        try:
            body = getter(spec['feed'])
            if spec['format'] == 'ics':
                entries, skipped = parse_ics(body, source)
            elif source == 'Fed':
                entries, skipped = parse_fed(body, now)
            else:
                entries, skipped = parse_ecb(body)
            latest = max(e['date'] for e in entries)
            local_today = now.astimezone(ZoneInfo(spec['zone'])).date().isoformat()
            meta.update(status='PARTIAL' if skipped else 'OK', latest_scheduled_date=latest,
                        skipped_events=skipped)
            if latest < local_today:
                meta['status'] = 'OUTDATED'
            selected = []
            for item in entries:
                if item['at_utc']:
                    when = datetime.fromisoformat(item['at_utc'])
                    upcoming = now <= when <= end
                else:
                    # Date-only sources keep their original calendar day. Never invent midnight or a release hour.
                    upcoming = local_today <= item['date'] <= end.astimezone(ZoneInfo(spec['zone'])).date().isoformat()
                if upcoming:
                    selected.append(item)
            meta['events'] = len(selected)
            return selected, meta
        except Exception:
            meta['message'] = 'Izvor nije učitan ili format nije prepoznat. Otvori zvanični kalendar.'
            return [], meta

    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(pool.map(read, SOURCES))
    unique = {}
    for rows, _ in results:
        for item in rows:
            key = (item['source'], item['date'], item['at_utc'], item['title'])
            unique[key] = item
    events = sorted(unique.values(), key=lambda e: (e['date'], e['at_utc'] or '', e['source'], e['title']))
    sources = [meta for _, meta in results]
    ok = sum(meta['status'] == 'OK' for meta in sources)
    return {'status': 'OK' if ok == len(SOURCES) else 'PARTIAL' if events or ok else 'UNAVAILABLE',
            'checked_at': now.isoformat(), 'window_end': end.isoformat(), 'days': days,
            'sources': sources, 'events': events}


def calendar_html(calendar):
    calendar = calendar or {}
    esc = lambda value: escape(str(value), quote=True)
    rows = []
    for item in calendar.get('events', []):
        if item.get('at_utc'):
            text = item['at_utc'].replace('T', ' ').replace('+00:00', ' UTC')
            stamp = f'<time data-local-time="{esc(item["at_utc"])}">{esc(text)}</time>'
        else:
            stamp = f'<time>{esc(item["date"])}</time><small>Satnica nije navedena · datum izvora</small>'
        spec = SOURCES.get(item.get('source'))
        if not spec:
            continue
        rows.append(f'<li class="calendar-event"><div class="event-date">{stamp}</div><div><a href="{esc(spec["page"])}" target="_blank" rel="noopener">{esc(item["label"])}</a><small>{esc(item["source"])} · {esc(item["title"])}</small></div></li>')
    status = calendar.get('status', 'UNAVAILABLE')
    checked = esc(calendar.get('checked_at', '—'))
    meta = []
    for source in calendar.get('sources', []):
        name = source['source']
        if name not in SOURCES:
            continue
        detail = f' · preskočeni zapisi: {source.get("skipped_events", 0)}' if source['status'] == 'PARTIAL' else ''
        meta.append(f'<li><a href="{esc(SOURCES[name]["page"])}" target="_blank" rel="noopener">{esc(name)}</a>: {esc(LABELS.get(source["status"], source["status"]))}{detail}</li>')
    empty = '<p>U učitanim rasporedima nema odabranih budućih objava u ovom periodu. To ne isključuje druge ili nenajavljene događaje.</p>'
    if status == 'UNAVAILABLE':
        empty = '<p>Kalendar nije dostupan. Ne možemo utvrditi naredne događaje iz ovog snimka.</p>'
    return f'''<section class="panel" id="economic-calendar"><span class="eyebrow">Odabrane zvanične objave</span>
<h2>Šta pratimo narednih {int(calendar.get('days', 30))} dana?</h2>
<p>{esc(LABELS.get(status, status))} · provjereno <time data-local-time="{checked}">{checked}</time></p>
<p class="muted" id="calendar-zone">Precizne satnice su u UTC; datum bez satnice ostaje datum iz zvaničnog izvora.</p>
<p id="calendar-stale" class="alert" hidden>Raspored je stariji od 36 sati. Provjeri noviji izvještaj ili zvanične kalendare prije oslanjanja na ove termine.</p>
<ul class="calendar-list">{''.join(rows)}</ul>{empty if not rows else ''}
<p class="muted">Raspored se osvježava uz dnevni izvještaj, nije praćenje uživo. Termini se mogu promijeniti. Kalendar ne obuhvata sve govore i nenajavljene vijesti; ne predviđa smjer kursa i ne mijenja zbir signala.</p>
<details><summary>Dostupnost kalendara po izvoru</summary><ul>{''.join(meta)}</ul></details></section>'''


def calendar_message(calendar, now):
    if not calendar:
        return []
    try:
        age = (now - datetime.fromisoformat(calendar['checked_at'])).total_seconds()
    except (KeyError, TypeError, ValueError):
        age = -1
    if not 0 <= age <= 36*3600 or calendar.get('status') == 'DEMO':
        return ['Kalendar nije svjež; provjeri novi izvještaj.']
    status = calendar.get('status')
    if status == 'UNAVAILABLE':
        return ['Kalendar nije dostupan; to ne znači da nema važnih objava.']
    lines = ['Naredne odabrane objave (satnice UTC):']
    if status != 'OK':
        lines.append('Dio izvora kalendara nedostaje.')
    rows = calendar.get('events', [])[:3]
    for item in rows:
        if item.get('at_utc'):
            stamp = datetime.fromisoformat(item['at_utc']).strftime('%d.%m. %H:%M UTC')
        else:
            stamp = date.fromisoformat(item['date']).strftime('%d.%m.') + ' (satnica nije navedena)'
        lines.append(f'• {stamp} — {item["label"]}')
    if not rows:
        lines.append('Nema odabranih objava u učitanim rasporedima za narednih 30 dana.')
    lines.append('Termini se mogu promijeniti; provjera je dnevna.')
    return lines
