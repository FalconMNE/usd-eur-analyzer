"""Free, explicit news rules for USD/EUR. No trained or calibrated forecast.

RSS text is inspected in memory. Only titles, links, attributions and structured
rule results leave the parser; article bodies are never republished.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

IBKR_PUBLISHER = "IBKR Traders' Insight"
IBKR_FEED = 'https://www.interactivebrokers.com/campus/traders-insight/?feed=news'
NEWS_HOSTS = {'www.federalreserve.gov', 'www.ecb.europa.eu',
              'www.interactivebrokers.com', 'ibkrcampus.com'}
NEWS_WINDOW_HOURS = 72
BIAS_LABELS = {'USD_UP_BIAS':'Uslovna podrška jačanju USD',
               'USD_DOWN_BIAS':'Uslovni pritisak na USD',
               'MIXED':'Suprotni uticaji u vijestima',
               'UNCLEAR':'Nema dovoljno jasnog uticaja iz vijesti'}
TOPIC_LABELS = {'inflation':'inflacija', 'employment':'zaposlenost',
                'growth':'privredna aktivnost', 'policy':'odluka o kamatama',
                'policy_expectations':'očekivanja kamatne politike'}
TOPIC_PATTERNS = {
    'inflation': r'\binflation\b|\bcpi\b|\bppi\b|\bpce\b|consumer pric|producer pric',
    'employment': r'\bpayrolls?\b|\bjobless claims\b|\bunemployment\b|\bemployment (?:data|report|situation)\b|\bjobs (?:data|report|growth)\b',
    'growth': r'\bgdp\b|\bretail sales\b|\bpmi\b|\beconomic growth\b',
}
REGIONS = {
    'US': r'(?-i:\bUS\b|\bU\.S\.?)|united states|\bamerican\b|\bfed\b|\bfomc\b|federal reserve|bureau of labor statistics|\bbls\b',
    'EU': r'\beuro\s?zone\b|\beuro area\b|\becb\b|european central bank|\beurostat\b',
    'OTHER': r'\bchina\b|\bchinese\b|\bjapan\b|\bjapanese\b|\bbritain\b|\buk\b|\bcanad(?:a|ian)\b|\baustralia\b|\bindia\b',
}
HIGH = r'(?:above|higher[ -]than|hotter[ -]than|stronger[ -]than|exceed(?:s|ed|ing)?|beat(?:s|ing)?|surpass(?:es|ed|ing)?)'
LOW = r'(?:below|lower[ -]than|cooler[ -]than|softer[ -]than|weaker[ -]than|miss(?:es|ed|ing)?)'
EXPECTATION = r'(?:expect(?:ed|ations?)|consensus|estimates?|forecasts?|anticipated|projections?)'
NEGATED = r'\b(?:not|never|neither|no longer|failed to|didn.t|doesn.t|isn.t|wasn.t)\b'
HYPOTHETICAL = r'\b(?:if|could|might|would|will|should|can|may|tomorrow|preview|expected to|projected to|forecast to|expects? to|likely to|plans? to)\b'
RISK_TERMS = r'\b(?:geopolitical|hormuz|war|military|credit crisis|credit risk|contagion|flight to safety)\b'


class NewsError(ValueError):
    pass


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.ignored = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.ignored += 1
        if not self.ignored and tag in ('p','div','br','li','h1','h2','h3','tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style') and self.ignored:
            self.ignored -= 1
        if not self.ignored and tag in ('p','div','li','h1','h2','h3','tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def plain_text(value):
    parser = PlainText()
    parser.feed(value[:200_000])
    text = ''.join(parser.parts)
    return '\n'.join(' '.join(line.split()) for line in text.splitlines() if line.strip())[:40_000]


def canonical_link(value, hosts=NEWS_HOSTS):
    try:
        url = urlsplit(value.strip())
        if url.scheme != 'https' or url.hostname not in hosts or url.username or url.password or url.port not in (None,443):
            return ''
    except ValueError:
        return ''
    # Known feeds link to path-addressed articles. Tracking parameters are not identity.
    return urlunsplit(('https', url.hostname, url.path, '', ''))


def region_of(text):
    hits = [region for region, pattern in REGIONS.items() if re.search(pattern,text,re.I)]
    return hits[0] if len(hits)==1 and hits[0]!='OTHER' else None


def event_feature(region, topic, pressure, kind):
    direction = pressure if region == 'US' else -pressure
    place = 'SAD' if region == 'US' else 'eurozoni'
    if topic == 'policy':
        action = 'povećanje' if pressure > 0 else 'smanjenje'
        rationale = f'Tekst opisuje {action} referentnih kamata. Uslovni kanal je promjena relativne privlačnosti te valute.'
    elif topic == 'policy_expectations':
        action = 'višim' if pressure > 0 else 'nižim'
        rationale = f'Komentar opisuje pomjeranje očekivanja ka {action} kamatama. To nije potvrđena odluka centralne banke.'
    else:
        if topic == 'employment':
            rationale = f'Tekst poredi podatke o zaposlenosti u {place} sa očekivanjima; iznenađenje može promijeniti očekivanja kamata.'
        else:
            position = 'iznad' if pressure > 0 else 'ispod'
            indicator = 'inflacija' if topic == 'inflation' else 'privredna aktivnost'
            rationale = f'Tekst navodi da je {indicator} u {place} {position} očekivanja; moguć uticaj je preko očekivanja kamata.'
    return {'region':region, 'topic':topic, 'event_key':region+':'+topic,
            'usd_direction':direction, 'kind':kind, 'reason':rationale}


def extract_events(title, body, publisher, published_at=None):
    official = publisher in ('Fed','Federal Reserve','ECB')
    default_region = 'US' if publisher in ('Fed','Federal Reserve') else 'EU' if publisher=='ECB' else region_of(title)
    content = (title+'\n'+body).replace('U.S.','US').replace('U.S','US')
    features = {}
    for paragraph in content.splitlines():
        # Stop standard article footers from generating economic interpretations.
        if re.search(r'^(?:disclosure|disclaimer|the above is provided|originally posted)',paragraph,re.I):
            continue
        region = region_of(paragraph) or default_region
        for sentence in re.split(r'(?<=[.!?])\s+',paragraph):
            if len(sentence)>1200:
                continue
            explicit = region_of(sentence)
            location = explicit or region
            if not location:
                continue
            # Do not assign US/EU effects to another economy or a mixed comparison.
            if re.search(REGIONS['OTHER'],sentence,re.I):
                continue
            if re.search(REGIONS['US'],sentence,re.I) and re.search(REGIONS['EU'],sentence,re.I):
                continue
            if re.search(NEGATED,sentence,re.I):
                continue
            historical = re.search(r'\b(?:last year|years ago|previous cycle|historically)\b',sentence,re.I)
            if published_at:
                historical = historical or any(int(year) < published_at.year for year in
                    re.findall(r'\b(?:in|during)\s+(20\d\d)\b', sentence, re.I))
            if historical:
                continue
            if re.search(HYPOTHETICAL,sentence,re.I):
                continue
            # A strictly described shift in market expectations is a separate kind,
            # never mislabeled as an actual central-bank decision.
            expectation = re.search(r'\b(reducing|reduced|lowering|lower|falling|raising|raised|increasing|higher|rising)\s+(?:the\s+)?(?:odds|chances|probability|expectations)\s+(?:of|for)\s+(?:fed|federal reserve|ecb)\s+(?:rate\s+)?(hikes?|cuts?)\b',sentence,re.I)
            if expectation:
                more = expectation[1].lower() in {'raising','raised','increasing','higher','rising'}
                pressure = (1 if more else -1) * (1 if expectation[2].lower().startswith('hike') else -1)
                item=event_feature(location,'policy_expectations',pressure,'COMMENTARY_EXPECTATION')
                features[(item['event_key'],item['usd_direction'],item['kind'])]=item
            decision = re.search(r'\b(?:fed|fomc|federal reserve|ecb|european central bank|governing council|committee)\b.{0,65}?\b(raised|increased|hiked|lowered|reduced|cut|decided to (?:raise|increase|hike|lower|reduce|cut))\b.{0,100}?\b(?:interest rates?|policy rates?|deposit (?:facility )?rate|target range|key rates?|federal funds rate)\b',sentence,re.I)
            if decision and not re.search(r'\b(?:expects?|expected|anticipates?|anticipated|probability|odds|likely|forecast|projected|priced in)\b', sentence, re.I):
                action=decision[1].lower().removeprefix('decided to ')
                pressure=1 if action.startswith(('rais','increas','hik')) else -1
                item=event_feature(location,'policy',pressure,'OFFICIAL_DECISION' if official else 'REPORTED_DECISION')
                features[(item['event_key'],item['usd_direction'],item['kind'])]=item
            higher = bool(re.search(HIGH+r'.{0,45}?'+EXPECTATION,sentence,re.I))
            lower = bool(re.search(LOW+r'.{0,45}?'+EXPECTATION,sentence,re.I))
            if higher == lower:
                continue
            if re.search(r'\b(?:earnings|profits?|revenues?|eps)\b', sentence, re.I):
                continue
            matched_topics=[topic for topic, pattern in TOPIC_PATTERNS.items() if re.search(pattern,sentence,re.I)]
            # A comparison cannot safely be attached to several different data
            # releases in the same sentence. Leave ambiguous prose unclassified.
            if len(matched_topics)!=1:
                continue
            for topic in matched_topics:
                if topic=='employment' and re.search(r'jobless claims|unemployment',sentence,re.I) and re.search(r'payroll|employment data|jobs growth',sentence,re.I):
                    continue
                pressure = 1 if higher else -1
                if topic=='employment' and re.search(r'jobless claims|unemployment',sentence,re.I):
                    pressure *= -1
                item=event_feature(location,topic,pressure,'REPORTED_SURPRISE')
                features[(item['event_key'],item['usd_direction'],item['kind'])]=item
    return list(features.values())


def parse_feed(body, publisher, now):
    if now.tzinfo is None:
        raise NewsError('News clock must include a time zone')
    if len(body)>4_000_000 or b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise NewsError('Unexpected RSS size or XML declarations')
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise NewsError('RSS is not valid XML') from exc
    channel = root.find('channel') if root.tag=='rss' else None
    if channel is None:
        raise NewsError('Not an RSS channel')
    ibkr = publisher == IBKR_PUBLISHER
    hosts = {'www.interactivebrokers.com','ibkrcampus.com'} if ibkr else {'www.ecb.europa.eu'} if publisher=='ECB' else {'www.federalreserve.gov'}
    output, seen_urls, seen_titles = [], set(), set()
    for item in channel.findall('item'):
        title = ' '.join(plain_text(item.findtext('title','')).split())[:280]
        link = canonical_link(item.findtext('link',''),hosts)
        if ibkr and '/campus/traders-insight/' not in urlsplit(link).path:
            continue
        try:
            stamp = parsedate_to_datetime(item.findtext('pubDate',''))
            if stamp.tzinfo is None:
                continue
            stamp = stamp.astimezone(timezone.utc)
        except (TypeError,ValueError,OverflowError):
            continue
        age = (now-stamp).total_seconds()
        title_key=re.sub(r'\W+',' ',title.casefold()).strip()
        if not title or not link or not 0<=age<=30*86400 or link in seen_urls or title_key in seen_titles:
            continue
        description = plain_text(item.findtext('description',''))
        full_text = plain_text(item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded',''))
        text = full_text or description
        categories = [plain_text(x.text or '') for x in item.findall('category')]
        # Prediction contracts, generic equity news and education are not observed
        # macroeconomic surprises, even if their titles contain "expectations".
        if ibkr and any('prediction market' in c.casefold() or 'trading education' in c.casefold() for c in categories):
            continue
        features = extract_events(title,text,publisher,stamp)
        topics=[topic for topic,pattern in TOPIC_PATTERNS.items() if re.search(pattern,title+' '+text,re.I)]
        relevant=bool(features or re.search(r'\b(?:fomc|fed|ecb|federal reserve|eurozone|eur/usd|usd/eur)\b',title+' '+description,re.I))
        if ibkr and not relevant:
            continue
        policy = bool(re.search(r'monetary policy|FOMC|interest rate|inflation|meeting of|discount rate|economic outlook',title,re.I))
        output.append({'publisher':publisher,'title':title,'url':link,'published_at':stamp.isoformat(),
                       'author':' '.join(plain_text(item.findtext('{http://purl.org/dc/elements/1.1/}creator','')).split())[:120],
                       'source_kind':'COMMENTARY' if ibkr else 'OFFICIAL_RELEASE',
                       'text_scope':'RSS_FULL_TEXT' if full_text else 'RSS_SUMMARY' if description else 'TITLE_ONLY',
                       'policy_related_title':policy,'recent_policy_release':not ibkr and policy and age<=48*3600,
                       'topics':topics,'events':features,
                       'risk_context':bool(re.search(RISK_TERMS,title+' '+text,re.I))})
        seen_urls.add(link);seen_titles.add(title_key)
    return sorted(output,key=lambda x:x['published_at'],reverse=True)[:12 if ibkr else 8]


def assess_news(news, now, unavailable_sources=()):
    groups, active_articles, risk_articles = {}, 0, 0
    for item in news:
        try:
            age=(now-datetime.fromisoformat(item['published_at'])).total_seconds()
        except (KeyError,TypeError,ValueError):
            continue
        if not 0<=age<=NEWS_WINDOW_HOURS*3600:
            continue
        active_articles+=1
        risk_articles+=bool(item.get('risk_context'))
        for feature in item.get('events',[]):
            group=groups.setdefault(feature['event_key'],{'region':feature['region'],'topic':feature['topic'],
                                    'directions':set(),'evidence':[]})
            group['directions'].add(feature['usd_direction'])
            evidence={'url':item['url'],'publisher':item['publisher'],'published_at':item['published_at'],
                      'kind':feature['kind'],'reason':feature['reason'],'usd_direction':feature['usd_direction']}
            if evidence not in group['evidence']:
                group['evidence'].append(evidence)
    events=[];directions=set()
    for key,group in sorted(groups.items()):
        values=group.pop('directions')
        directions.update(values)
        events.append({'event_key':key,**group,'usd_direction':next(iter(values)) if len(values)==1 else 0,
                       'conflicting':len(values)>1,'evidence':group['evidence'][:6]})
    bias='MIXED' if len(directions)>1 else 'USD_UP_BIAS' if directions=={1} else 'USD_DOWN_BIAS' if directions=={-1} else 'UNCLEAR'
    return {'method':'explicit_text_rules_v1','window_hours':NEWS_WINDOW_HOURS,
            'bias':bias,'label':BIAS_LABELS[bias],'active_articles':active_articles,
            'event_groups':len(events),'events':events,'risk_articles':risk_articles,
            'unavailable_sources':list(unavailable_sources),
            'coverage':'PARTIAL' if unavailable_sources else 'OK',
            'accuracy_validated':False,
            'meaning':'Uslovno tumačenje javnog teksta, bez kalibrisane vjerovatnoće. Tekstovi o istoj oblasti su grupisani; broj članaka ne dodaje glasove.'}


def combine_outlooks(outlooks, context):
    """News may veto agreement; it never boosts scores or invents a direction."""
    result=[]
    bias=context['bias']
    for item in outlooks:
        base=item['direction'];direction=base
        reason='BASE_ONLY'
        if base in ('USD_UP_BIAS','USD_DOWN_BIAS'):
            if bias=='MIXED' or bias in ('USD_UP_BIAS','USD_DOWN_BIAS') and bias!=base:
                direction='UNCLEAR';reason='NEWS_CONFLICT'
            elif bias==base:
                reason='ALIGNED'
        result.append({'horizon_reference_observations':item['horizon_reference_observations'],
                       'base_direction':base,'direction':direction,'reason':reason})
    return result


def news_message(context):
    if not context:
        return []
    lines=['Vijesti (posljednja 72 sata): '+context['label']+'.']
    if context.get('risk_articles'):
        lines.append('Prisutan je i kontekst geopolitičkog ili kreditnog rizika; njegov smjer nije automatski određen.')
    if context.get('unavailable_sources'):
        lines.append('Dio izvora vijesti nije učitan.')
    lines.append('Procjena iz teksta je eksperimentalna; ne predstavlja potvrđenu prognozu.')
    return lines
