# USD/EUR — analiza bez uključenog PC-a

Ovaj paket prenosi postojeći USD/EUR Analyzer 0.1.0 na GitHub Actions.
Python i preuzimanje podataka rade na GitHub serveru; na telefonu otvaraš
objavljeni izvještaj. Tvoj PC, Python na telefonu i TWS nisu potrebni.

**Status paketa:** spreman za postavljanje. Nijedan repozitorijum, sajt,
raspored ili Telegram kanal nije aktiviran samim preuzimanjem ovog ZIP-a.

## Predložena postavka

- **GitHub Actions** pokreće analizu jednom dnevno, predloženo u **17:37 UTC**.
  To je 10:37 u zoni UTC−7; u Crnoj Gori 19:37 ljeti i 18:37 zimi.
  Vrijeme se mijenja u `.github/workflows/daily-analysis.yml`.
- **GitHub Pages** prikazuje posljednji izvještaj na telefonu, uz datum kursa
  i datum obrade. Objavu uključuješ posebno.
- **Telegram** može dostaviti privatnu poruku s kursom, procjenom sedmice i
  mjeseca i linkom. Slanje je isključeno dok se izričito ne uključi.
- Svaka procjena je eksperimentalna. Ovo nije automatsko trgovanje.

Predloženi raspored nije garantovan tačan termin. GitHub može odložiti ili
preskočiti zakazano pokretanje pri opterećenju. U javnom repozitorijumu može
isključiti raspored nakon 60 dana bez aktivnosti. Povremeno provjeri Actions
i datum izvještaja. Alat nije namijenjen intradnevnim signalima.

## Izbor vidljivosti prije objave

Na GitHub Free, Pages je dostupan za javne repozitorijume. Na odgovarajućem
plaćenom planu izvorni repozitorijum može biti privatan, ali Pages stranica
je i dalje uobičajeno javna; privatno objavljivanje ima posebne uslove.
Ne pretpostavljaj da privatni repozitorijum znači privatnu stranicu.

Paket objavljuje samo javne tržišne podatke i metodologiju. U repozitorijum
ne stavljaj izvode računa, podatke o stanovima, fotografije računa, lozinke
ili tokene. Iznosi kalkulatora obrađuju se u telefonu, ne šalju se serveru
i ne čuvaju se u izvještaju. Nema analitike praćenja posjetilaca.

Ako želiš privatne rezultate bez javne stranice, koristi privatan
repozitorijum + Telegram i ostavi `ENABLE_PAGES` isključeno. Actions minute
u privatnim repozitorijumima zavise od plana i potrošnje. Za privatnu web
aplikaciju s prijavom potreban je dodatni sloj pristupa.

## Jednokratno postavljanje na GitHub

1. Napravi **novi, odvojeni** repozitorijum, predloženi naziv `usd-eur-analyzer`.
   Izaberi vidljivost svjesno; nije potrebno mijenjati neki postojeći projekat.
2. U njegov korijen postavi **sadržaj** foldera `USD_EUR_GitHub`, uključujući
   `.github/workflows/daily-analysis.yml`. Nemoj postaviti samo ZIP ili cijeli
   paket kao dodatni ugniježđeni folder. Podrazumijevana grana je `main`.
3. Za stranicu otvori **Settings → Pages → Build and deployment → Source →
   GitHub Actions**. Ako Pages nije dostupan za odabranu vidljivost/plan,
   ne mijenjaj vidljivost naslijepo: izaberi drugi način prikaza.
4. U **Settings → Secrets and variables → Actions → Variables** dodaj
   `ENABLE_PAGES` sa vrijednošću `true`, samo ako želiš objavu.
5. Otvori **Actions → USD EUR daily analysis → Run workflow**.
   Poslije uspješnog `Deploy Pages` koraka, link je u **Settings → Pages**.
6. Otvori link na telefonu. U browseru možeš dodati prečicu na početni ekran.

Može se postaviti kroz GitHub web interfejs ili povezani GitHub nalog.
Telefon može upravljati repozitorijumom; ZIP se mora raspakovati jer GitHub
ne izvršava kod koji je ostavljen unutar arhive. Prikaz skrivenog `.github`
foldera zavisi od aplikacije za fajlove. Ako upload izostavi taj folder,
workflow neće postojati.

`push` na `main`, ručno pokretanje i dnevni raspored pokreću isti postupak.
Rezultat se čuva i kao Actions artefakt `usd-eur-report` sedam dana. Raspored
počinje raditi tek kada je workflow na podrazumijevanoj grani i Actions je
omogućen. Za fork je obično potrebno dodatno omogućiti zakazane workflow-e.

## Opciona Telegram obavještenja

Potrebni su tvoj Telegram nalog, bot koji napraviš kroz zvanični **@BotFather**,
i ID tvog privatnog razgovora sa tim botom. Prvo otvori bot i pošalji `/start`.
ID se može provjeriti kroz zvanični `getUpdates` odgovor; detalj ovog koraka
možemo zajedno završiti bez slanja tokena u chat. Ne koristi tuđi ili grupni ID.

U **Settings → Secrets and variables → Actions → Secrets** dodaj:

| Secret | Sadržaj |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token tvog bota iz BotFather-a |
| `TELEGRAM_CHAT_ID` | Pozitivan broj tvog privatnog razgovora |

Tek kada su oba unosa provjerena, u **Variables** dodaj `ENABLE_TELEGRAM=true`.
Sljedeće pokretanje šalje poruku, uključujući ručna ponovna pokretanja.
Ako raspored ili cijeli workflow ne uspiju početi, sam alat ne može poslati
obavještenje o tom neizvršenom pokretanju; tada provjeri GitHub Actions.
Zvuk i prikaz na zaključanom telefonu zavise od dozvola za Telegram.

Token se ne upisuje u kod, HTML, README ili poruku ovdje. Program ne slijedi
preusmjerenja i ne ispisuje URL greške, jer Telegram URL sadrži token.
Slanje se ne ponavlja automatski pri nejasnom odgovoru kako se ne bi slale
duple poruke. Poruke nisu testirane na stvarnom nalogu u ovom paketu.

Isključenje: postavi `ENABLE_TELEGRAM=false`. Za zaustavljanje cijelog
rasporeda otvori Actions i izaberi **Disable workflow**.

## Šta je sa Firebase-om?

Firebase Hosting može prikazivati isti generisani `public` folder; priložen
je `firebase.json`. Hosting sam ne pokreće Python. Moguće je kombinovati
GitHub Actions za obračun i Firebase Hosting za stranicu, ali treba povezati
tačan Firebase projekat i podesiti ovlašćenje za deploy. To u ovom paketu
nije aktivirano niti je dodat Firebase deploy workflow.

Potpuno Firebase rješenje koristi Cloud Functions/Cloud Run i Scheduler;
za Functions objavu potreban je **Blaze** plan sa povezanim billing nalogom.
To je dodatna postavka i potencijalni trošak; nije potrebno za GitHub opciju.
Firebase Hosting bez serverskih funkcija ima drugačije kvote i uslove.

## Model, greške i provjera

Kurs: ECB; kamate: New York Fed EFFR i ECB €STR; inflacija: BLS i ECB HICP;
naslovi: zvanični Fed i ECB RSS. Preračunava se **EUR za 1 USD**, tako da
rast prikazanog kursa znači jačanje dolara. Detalji su u `MODEL.md`.

Nedostaju li osnovni podaci, objavljuje se poruka bez važeće prognoze, a
workflow na kraju označava grešku. Ako GitHub ne uspije objaviti ni tu stranicu,
prethodni snimak ostaje: nakon 36 sati prikazuje upozorenje i skriva kartice
procjene smjera. Referentni podaci i njihovi datumi ostaju vidljivi.
Osvježavanje browsera učitava snimak; ne pokreće novu analizu.

Lokalne komande za razvoj (nisu potrebne za svakodnevnu upotrebu telefonom):

```text
python -m unittest discover -s tests -v
python build_cloud.py --demo
python build_cloud.py
python notify_telegram.py --preview
```

Provjera koda ne potvrđuje tačnost tržišnih prognoza. Ovaj model nije
validiran kao profitabilna strategija; nema ciljne cijene ili procenta uspjeha.

## Zvanična dokumentacija

- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- https://core.telegram.org/bots/api#sendmessage
- https://firebase.google.com/docs/functions/get-started
- https://firebase.google.com/docs/functions/schedule-functions
