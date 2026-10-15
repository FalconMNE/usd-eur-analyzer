"""Opt-in private-chat notifications. Tokens are read only from the environment."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from fx_report import LABELS, STATUS
from fx_calendar import calendar_message


def message(report, page_url='', now=None):
    now = now or datetime.now(timezone.utc)
    try:
        created = datetime.fromisoformat(report['generated_at'])
        age = (now-created).total_seconds()
        fresh = 0 <= age <= 36*3600
    except (KeyError,TypeError,ValueError):
        fresh = False
    demo = report.get('source_mode') != 'PUBLIC_DATA'
    good = fresh and not demo and report.get('status') in ('OK','PARTIAL_CONTEXT')
    lines = ['USD/EUR · dnevni pregled', 'Izrada: '+str(report.get('generated_at','—'))]
    if not good:
        lines.append('Nema važeće nove procjene. Podaci nedostaju, zastarjeli su ili su demonstracioni.')
    else:
        rate = report.get('eur_per_usd')
        if not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate <= 0:
            raise ValueError('Invalid report rate')
        lines.append(f"1 USD = {rate:.5f} EUR (ECB referenca {report.get('reference_date','—')})")
        for item in report.get('outlooks',[]):
            horizon = 'Sedmica' if item['horizon_reference_observations']==5 else 'Mjesec'
            lines.append(f"{horizon}: {LABELS.get(item['direction'],'Nema jasnog smjera')} ({item['score']:+d}/4)")
        lines.append(STATUS.get(report['status'],report['status']))
        lines.extend(calendar_message(report.get('calendar'), now))
    lines.append('Procjena nije potvrđena prognoza ni nalog za trgovanje. Zbir nije vjerovatnoća.')
    if page_url:
        parsed = urlsplit(page_url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or any(c in page_url for c in '\r\n'):
            raise ValueError('Site link must be a plain HTTPS URL')
        lines.append(page_url)
    return '\n'.join(lines)[:4000]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(text, token, chat_id, opener=None):
    if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{20,120}', token or ''):
        raise ValueError('Telegram token is missing or malformed')
    # A positive numeric ID is a personal chat; groups and channels are excluded.
    if not re.fullmatch(r'[1-9][0-9]{0,19}', chat_id or ''):
        raise ValueError('A personal Telegram chat ID is required')
    payload = json.dumps({'chat_id':chat_id,'text':text,'link_preview_options':{'is_disabled':True}},ensure_ascii=False).encode('utf-8')
    req = Request('https://api.telegram.org/bot'+token+'/sendMessage', data=payload, headers={'Content-Type':'application/json'}, method='POST')
    # No automatic retry: a timed-out send could already have been delivered.
    opener = opener or build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=20) as response:
            result = json.loads(response.read(65536))
        if result.get('ok') is not True:
            raise RuntimeError('Telegram rejected the message')
    except Exception:
        # Never print exception URLs: the URL contains the secret token.
        raise RuntimeError('Telegram delivery could not be confirmed; check secrets and your private chat. No automatic retry.') from None


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--report',type=Path,default=Path('public/report.json'))
    p.add_argument('--preview',action='store_true')
    args=p.parse_args()
    try:
        report=json.loads(args.report.read_text(encoding='utf-8'))
        text=message(report,os.getenv('SITE_URL',''))
        if args.preview:
            print(text)
            return 0
        if os.getenv('ENABLE_TELEGRAM','').lower()!='true':
            print('Telegram is disabled. Use --preview to inspect a message without sending.')
            return 0
        send(text,os.getenv('TELEGRAM_BOT_TOKEN',''),os.getenv('TELEGRAM_CHAT_ID',''))
        print('Telegram confirmed delivery.')
        return 0
    except (Exception,):
        print('Notification failed. Check report, private chat ID and repository secrets. Credentials are never printed.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
