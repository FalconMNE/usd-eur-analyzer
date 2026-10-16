# Provjera nadogradnje 0.4.0

Datum: 16.10.2026. Osnova: javna grana main projekta
FalconMNE/usd-eur-analyzer, commit `9697f95f541897bd656e965f3bde31e987c707cb`.
Prije pakovanja potvrđeno je da je to i dalje posljednji javni commit.

## Automatske provjere

- 79 Python testova: 51 postojeći, 19 provjera vijesti i 9 BLS rezerve.
- Provjerene su suprotne USD/EUR interpretacije američkih i eurozonskih
  podataka, obrtanje znaka kod nezaposlenosti, negacije, hipotetičke rečenice,
  određena istorijska poređenja, svježina i grupisanje ponovljenih tekstova.
- Provjereno je da tijelo RSS članka utiče na klasifikaciju, ali ne ulazi
  u izlazni JSON. Nepouzdani linkovi, budući datumi i XML deklaracije se odbijaju.
- Vijesti ne povećavaju osnovni skor i ne pretvaraju neodređen osnovni signal
  u jasan. Neslaganje može samo ublažiti postojeći jasan smjer. Web i Telegram
  koriste isti završni zaključak. Nedostajući izvor ostaje vidljiv.
- BLS: mjesečna rezerva, nepotpuna pokrivenost, neispravni redovi/satnice,
  promjena godine, datum bez satnice, ljetnje/zimsko vrijeme i ograničen retry.
- JavaScript je izvršen u Node VM za Europe/Podgorica i America/Los_Angeles:
  lokalizacija satnica, kalkulator i skrivanje kartica smjera i panela
  tumačenja vijesti poslije 36 sati.
- `git diff --check`: bez grešaka razmaka/formatiranja zakrpe.

## Stvarni javni izvori

Izrada izvještaja počela je `2026-10-16T02:05:06.805019+00:00`:

- Svih osam izvora dostupno; osnovni status `OK`, bez `source_errors`.
- Kursni datum: 15.10.2026; to je datum ECB reference, ne vrijeme kursa uživo.
- Svih pet kalendara dostupno, ukupno 14 odabranih budućih događaja.
- IBKR RSS: pet izdvojenih komentara, tekst članka dostupan u RSS-u.
  Zajedno sa svježim Fed/ECB objavama, osam objava ulazi u prozor od 72 sata.
- Tri oblasti sa prepoznatim uticajima; novinski kontekst `MIXED`.
  Osnovni mjesečni smjer `USD_UP_BIAS` postao je završni `UNCLEAR` zbog
  suprotnih prepoznatih uticaja. To je opažanje rada pravila, ne provjera tržišnog ishoda.
- Zasebno su stvarno učitane BLS mjesečne stranice za oktobar i novembar:
  osam prepoznatih odabranih zapisa prije filtriranja prošlih datuma,
  bez preskočenih zapisa ili nedostupnih mjeseci.
- Telegram tekst je pregledan lokalno. Poruka nije poslata iz ovog okruženja.

Svježa provjera dostupnosti ne garantuje buduću dostupnost. Prvobitni BLS
prekid nije reprodukovan i njegov uzrok nije pouzdano utvrđen. Rezerva je
provjerena kao dodatni put do zvaničnih rasporeda, ne kao garancija uklanjanja
svih mogućih mrežnih grešaka.

## Šta još nije potvrđeno

Ova verzija nije postavljena na korisnikov GitHub. Nisu izvršeni GitHub-hosted
testovi ove verzije, njeno objavljivanje ili slanje nove Telegram poruke.
Postojeći workflow sa rasporedom 16:07 Europe/Podgorica nije mijenjan;
uspješnost njegovog narednog zakazanog pokretanja treba provjeriti u Actions.

Chromium nije dostupan u razvojnom okruženju. Provjereni su generisani HTML,
obrada teksta i izvršavanje JavaScript-a, ali nije napravljen vizuelni screenshot
mobilnog prikaza ove verzije.

**Nije mjerena prognostička tačnost.** Testovi provjeravaju konkretne slučajeve
rada programa; ne potvrđuju da pravila obuhvataju sav prirodni jezik, da vijesti
poboljšavaju prognozu ili da postoji profitabilna trgovačka strategija.
