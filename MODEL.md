# Metodologija USD/EUR Analyzer 0.1.0

## Šta znače rezultati

- **Prednost scenariju jačanja USD**: pravila trenutno daju više podrške rastu
  dolara u odnosu na euro. To nije obećanje da će dolar porasti.
- **Prednost scenariju slabljenja USD**: pravila više podržavaju suprotan smjer.
- **Nema jasnog smjera**: signali su slabi ili se međusobno suprotstavljaju.
- **Nedovoljno podataka**: nedostaju svježi kurs ili uporedive kamatne stope.
  Nema objedinjene procjene smjera.
- **Dio dodatnih podataka nedostaje**: osnovna procjena može biti prikazana,
  ali npr. inflacija ili RSS nije dostupna. Greška je navedena u izvještaju.

Glavni prikaz je **EUR za 1 USD**. Ako raste sa 0.89 na 0.90, dolar jača:
1,000 USD vrijedi 900 umjesto 890 EUR, prije troškova. Na uobičajenom
EUR/USD grafikonu isto jačanje dolara odgovara padu EUR/USD.

Zbir −4 do +4 je zbir pravila, **nije procenat vjerovatnoće**. Nije testirano
da ova pravila daju uspješne prognoze ili profit. Alat ne šalje naloge niti
se povezuje sa brokerskim računom.

## Izvori

- **ECB EXR**: dnevni referentni EUR/USD kurs, pravilno preračunat u USD/EUR.
- **New York Fed**: EFFR, efektivna američka noćna kamatna stopa.
- **ECB €STR**: noćna kamatna stopa eurozone; poređenje sa EFFR je na istim datumima.
- **BLS CPI-U**: američki indeks cijena, iz kojeg se računa godišnja inflacija.
- **ECB/Eurostat HICP**: godišnja inflacija eurozone, nova HICP serija od 2026.
- **Fed i ECB RSS**: naslovi novijih zvaničnih objava i linkovi za čitanje.

ECB kurs je dnevna referentna vrijednost, ne živa ponuda za konverziju ili
trgovanje. ECB ga objavljuje informativno. Stvarni bankarski/brokerski kurs
i troškovi mogu biti drugačiji. Alat nije namijenjen intradnevnom trgovanju.

Inflacija se poredi za isti mjesec, jer SAD i eurozona objavljuju različitim
danima. CPI i HICP imaju različite korpe. HICP oznaka E znači procijenjena
vrijednost. Inflacija je dodatni kontekst; veća inflacija ne daje automatski
glas za jačanje ili slabljenje valute.

RSS dio prikazuje naslove i označava novije naslove povezane sa monetarnom
politikom. Ne analizira kompletne članke, ne provjerava tržišni konsenzus
i ne pokušava da svaki govor prevede u kupovni/prodajni signal.

## Detalji i ograničenja modela

Za sedmicu se koriste momentum kroz 5 objava, SMA5 prema SMA20 i posljednji
kurs prema SMA20. Za mjesec se koriste momentum kroz 20 objava, SMA20 prema
SMA50 i posljednji kurs prema SMA50. Svaki daje −1, 0 ili +1; povezani su
međusobno i nisu nezavisni dokazi.

Prag momentuma je veći od: 0.10% za 5 objava / 0.25% za 20 objava, ili
0.5 × dnevna volatilnost × kvadratni korijen broja objava. Volatilnost je
standardna devijacija do 60 logaritamskih dnevnih promjena. Trend SMA prag
je 0.05% / 0.15%, a kurs/SMA prag 0.05% / 0.10% za kraći/duži horizont.

Četvrti glas potiče od promjene razlike EFFR minus €STR kroz 20 zajedničkih
objava: više od +0.10 procentnih poena daje +1, manje od −0.10 daje −1,
ostalo nulu. Viša postojeća američka kamata sama po sebi ne daje glas.
Kamatni nivo može već biti uračunat u kurs; ovaj jednostavan odnos nije zakon.

Zbir najmanje +3 daje prednost jačanju USD; najviše −3 daje prednost
slabljenju. Ostali rezultati su neodređeni. Horizonti su približni: računaju
se naredne ECB dnevne objave, ne fiksan broj kalendarskih dana.

Potrebno je najmanje 60 kursnih podataka, posljednji ne stariji od 5 kalendarskih
dana. Kamatne stope i njihov zajednički datum ne smiju biti stariji od 7 dana.
Inflacija i zajednički mjesec ne smiju biti stariji od 100 dana od kraja mjeseca.
Ove granice omogućavaju vikende/praznike, a ne znače da je kurs trenutno izvršiv.

Nema prognozirane ciljne cijene, pouzdanog procenta uspjeha, optimizacije
parametara, backtesta pune strategije, terminskih kamatnih očekivanja,
anketa analitičara, pune geopolitičke analize ili kompletnog budućeg kalendara.
Model ne raspoređuje tvoj novac i ne preporučuje iznos konverzije.

Dokumentacija izvora:

- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- https://data.ecb.europa.eu/help/api/overview
- https://www.newyorkfed.org/markets/reference-rates/effr
- https://www.bls.gov/developers/api_signature_v2.htm
- https://data.ecb.europa.eu/data/datasets/HICP/HICP.M.U2.N.000000.4D0.ANR
- https://www.ecb.europa.eu/home/html/rss.en.html
- https://www.federalreserve.gov/feeds/feeds.htm
