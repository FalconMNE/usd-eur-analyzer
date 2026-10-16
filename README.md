# USD/EUR — analiza bez uključenog PC-a

Cloud verzija 0.4.0 dodaje provjeru teksta vijesti i rezervni BLS kalendar
postojećem USD/EUR analizatoru na GitHub Actions.
Python i preuzimanje podataka rade na GitHub serveru; na telefonu otvaraš
objavljeni izvještaj. Tvoj PC, Python na telefonu i TWS nisu potrebni.

**Status paketa:** spreman za postavljanje. Nijedan repozitorijum, sajt,
raspored ili Telegram kanal nije aktiviran samim preuzimanjem ovog ZIP-a.

## Novo u verziji 0.4.0

- Javni IBKR Traders' Insight RSS, uz postojeće Fed i ECB objave. Nema
  veze sa TWS-om, brokerskim računom, plaćenim vijestima ili IBKR API-jem.
- Provjera raspoloživog teksta iz posljednja 72 sata: odluke o kamatama,
  opisane promjene očekivanja i izričita poređenja ekonomskih podataka
  sa očekivanjima. To su ograničena pravila za engleski tekst, ne AI servis.
- Odvojeni su zvanično saopštenje, tržišni komentar i procjena iz teksta.
  Naslov, autor kada postoji, datum i link ostaju vidljivi. Tijelo članka
  obrađuje se u memoriji i ne objavljuje se u izvještaju.
- Ako prepoznati uticaji proturječe jasnom osnovnom smjeru, završni zaključak
  postaje „Nema jasnog smjera”. Saglasnost ne povećava skor. Broj ponovljenih
  članaka ne dodaje glasove. Web i Telegram prikazuju isti završni zaključak.
- Ako BLS ICS ne radi ili je neupotrebljiv, pokušavaju se zvanični mjesečni
  rasporedi. Nedostajući mjesec ili zapis ostaje označen kao djelimičan izvor.
- Nema novih pretplata, API ključeva ili naplate za servis analize vijesti.
  Postojeće postavke GitHub-a i Telegram-a koriste se kao ranije.

**Veća tačnost još nije potvrđena.** Ova verzija proširuje kontekst i pokazuje
neslaganja. Pravila mogu propustiti vijest ili pogrešno protumačiti tekst.
Za tvrdnju o većoj tačnosti potrebno je poređenje sa budućim ishodima;
prolazak testova programa to ne dokazuje. Detalji i granice su u `MODEL.md`.

## Postojeće funkcije kalendara

- Odabrane zakazane objave za narednih 30 dana: BLS, BEA, Eurostat, Fed i ECB.
- Status svakog kalendara; nedostupan izvor ne znači da nema događaja.
- Satnice koje izvor objavi prikazuju se u vremenskoj zoni uređaja.
  Ako izvor objavi samo datum, ne izmišljamo satnicu niti mijenjamo taj datum.
- Dnevna Telegram poruka uključuje do tri naredna događaja; poznate satnice
  u poruci su izričito označene kao UTC. To nisu posebna upozorenja neposredno
  prije objave. Raspored se osvježava kada se izvrši dnevna analiza.
- Kurs je jasnije označen kao dnevna ECB referenca. Wise i TradingView nisu
  povezani. Datum kursa ostaje odvojen od vremena izrade izvještaja.
- Kalendar je dodatni kontekst i ne mijenja postojeće ocjene smjera.

Ako projekat već radi, koristi paket za nadogradnju i njegovo uputstvo;
nema potrebe ponavljati početno podešavanje Pages-a, tokena ili rasporeda.

## Predložena postavka

- **GitHub Actions** je podešen za radne dane u **16:07 Europe/Podgorica**.
  Koristi `cron: '7 16 * * 1-5'` i `timezone: 'Europe/Podgorica'` u
  `.github/workflows/daily-analysis.yml`. Zona prati ljetnje/zimsko vrijeme.
  Ova nadogradnja ne mijenja taj fajl. Predviđeno vrijeme nije potvrda
  da je pojedinačno zakazano pokretanje zaista izvršeno: to se vidi u Actions.
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
duple poruke. Novi format poruke u ovoj verziji provjeren je bez slanja.

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
tekstovi vijesti: javni Fed, ECB i IBKR Traders' Insight RSS;
kalendari: BLS, BEA, Eurostat, Fed i ECB.
Preračunava se **EUR za 1 USD**, tako da
rast prikazanog kursa znači jačanje dolara. Detalji su u `MODEL.md`.

Nedostaju li osnovni podaci, objavljuje se poruka bez važeće prognoze, a
workflow na kraju označava grešku. Ako GitHub ne uspije objaviti ni tu stranicu,
prethodni snimak ostaje: nakon 36 sati prikazuje upozorenje i skriva kartice
procjene smjera i panel tumačenja vijesti. Referentni podaci i njihovi datumi ostaju vidljivi.
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
