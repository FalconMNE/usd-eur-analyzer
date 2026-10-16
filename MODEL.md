# Metodologija USD/EUR Analyzer Cloud 0.4.0

Osnovni model kursa i kamata ostaje verzija 0.1.0. Novi sloj vijesti koristi
metod `explicit_text_rules_v1`; nije treniran niti statistički kalibrisan.

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
- **Fed i ECB RSS**: novije zvanične objave, njihov raspoloživi RSS tekst i linkovi.
- **IBKR Traders' Insight**: javni RSS sa komentarima različitih autora;
  nije privatni izvor vijesti sa brokerskog računa. Komentar nije potvrda činjenice.

ECB kurs je dnevna referentna vrijednost, ne živa ponuda za konverziju ili
trgovanje. ECB ga objavljuje informativno. Stvarni bankarski/brokerski kurs
i troškovi mogu biti drugačiji. Alat nije namijenjen intradnevnom trgovanju.

Inflacija se poredi za isti mjesec, jer SAD i eurozona objavljuju različitim
danima. CPI i HICP imaju različite korpe. HICP oznaka E znači procijenjena
vrijednost. Inflacija je dodatni kontekst; veća inflacija ne daje automatski
glas za jačanje ili slabljenje valute.

RSS dio prikazuje naslov, izvor, autora kada postoji i datum. Provjerava
tekst dostavljen u RSS-u: sadržaj članka kada postoji, inače sažetak ili
samo naslov. Ne otvara automatski pune stranice članaka, ne provjerava
nezavisno tržišni konsenzus i ne daje naloge za trgovanje.

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

Osnovni zbir najmanje +3 daje prednost jačanju USD; najviše −3 daje prednost
slabljenju. Ostali osnovni rezultati su neodređeni. Sloj vijesti opisan ispod
može ublažiti jasan zaključak u neodređen. Horizonti su približni: računaju
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

## Kalendar — Cloud 0.3.0

Kalendar se ponovo preuzima pri svakoj izradi izvještaja. Prikazuje narednih
30 dana, iz odabranih javnih rasporeda:

- BLS: CPI, PPI, Employment Situation, JOLTS i Employment Cost Index.
- BEA: nacionalni BDP i Personal Income and Outlays, koji uključuje PCE.
- Eurostat: inflacija/HICP, BDP/zaposlenost i nezaposlenost.
- Fed: završni dan redovnog sastanka FOMC, iz zvanične stranice.
- ECB: završni dan sastanka o monetarnoj politici. Nemonetarni sastanci
  i prvi dan dvodnevnog sastanka nisu ponovljeni kao zasebni događaji.

To je raspored, ne rezultat objave ili tržišni konsenzus. Sam datum događaja
ne učestvuje u zbiru −4 do +4 niti određuje smjer. Tekst vijesti o već
objavljenom podatku zasebno prolazi kroz pravila opisana ispod.

ICS vremenske zone se računaju uz ljetnje/zimsko vrijeme. Ako izvor navede
samo datum, zapis ostaje bez satnice; ne pretpostavlja se uobičajeni sat.
Datum-only događaj ostaje prikazan tokom tog datuma u zoni izvora. Na webu
se precizna vremena prikazuju u zoni uređaja, a u Telegram poruci u UTC.

Otkazani ICS događaji se izostavljaju, a novija verzija istog UID-a zamjenjuje
stariju. Nepodržani ponavljajući događaji ili satnice označavaju djelimičan
izvor. Ako izvor ne radi, ima neprepoznatljiv format ili raspored sadrži samo
prošlost, prikazuje se status umjesto izmišljanja novih datuma. Izvještaj
ne tvrdi da pokriva sve događaje, govore ili nenajavljene vijesti.

Pošto su rasporedi promjenljivi, korisnik treba provjeriti izvor prije
oslanjanja na termin. Nakon 36 sati web prikazuje upozorenje na stari raspored.
Kod izvora sa HTML formatom promjena strukture može zahtijevati izmjenu parsera.

Zvanični kalendari:
- https://www.bls.gov/schedule/news_release/
- https://www.bea.gov/news/schedule/icalendar
- https://ec.europa.eu/eurostat/subscribe/ics.format
- https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html

## Rezervni BLS raspored — Cloud 0.4.0

Glavni izvor ostaje BLS ICS. Privremeni HTTP problemi (408, 429, odabrani
5xx) ili mrežni prekid imaju najviše jedan ponovni pokušaj. Odbijeni pristup
se ne zaobilazi. Ako glavni izvor ne radi, ima preskočene zapise ili samo
prošle događaje, pokušavaju se zvanične List View stranice za sve mjesece
koje obuhvata prozor od 30 dana:

`https://www.bls.gov/schedule/GODINA/MJESEC_sched_list.htm`

Parser zahtijeva prepoznatljivu tabelu, datume traženog mjeseca i potvrdu
da je satnica Eastern Time. Računa America/New_York sa DST pravilima.
Nedostajući mjesec ili neprepoznata satnica označava djelimičan izvor.
Ako ni rezerva ne radi, dostupni zapisi i njihova upozorenja ostaju vidljivi;
nema kopiranja prošlogodišnjih datuma. Promjena strukture izvora i dalje
može zahtijevati popravku parsera. Prvobitni povremeni prekid nije reprodukovan;
rezervni izvor smanjuje zavisnost od jednog formata, ne garantuje dostupnost.

## Kako vijesti utiču na zaključak

1. Prihvataju se HTTPS linkovi poznatih izdavača, valjan datum sa vremenskom
   zonom i najviše 30 dana starosti. Budući datumi se preskaču. Po izvještaju
   se zadržava najviše 12 IBKR i po 8 Fed/ECB stavki iz dostupnog RSS-a.
2. Na tumačenje smjera utiču samo objave stare do **72 sata** u trenutku izrade.
   To je starost objave, ne pouzdano utvrđena starost svakog događaja u tekstu.
3. Engleski tekst se provjerava ograničenim, eksplicitnim pravilima:
   opisano povećanje/smanjenje referentne kamate; opisano pomjeranje izgleda
   za Fed/ECB povećanja/smanjenja; ili podatak o inflaciji, zaposlenosti ili
   aktivnosti izričito iznad/ispod očekivanja. Samo „inflacija raste” nije dovoljno.
4. Pravila pretpostavljaju uslovni kanal očekivanja kamata: jači američki
   podatak može podržati USD, jači podatak eurozone može podržati EUR.
   Za nezaposlenost/zahtjeve za naknadu znak se obrće. To nije ekonomski zakon.
   Očekivana odluka može već biti ugrađena u kurs, pa ni stvarna promjena
   kamate sama po sebi ne dokazuje budući smjer.
5. Preskaču se prepoznate negacije, uslovne/buduće rečenice i određena
   istorijska poređenja, nejasna kombinacija više pokazatelja i poređenja
   drugih ekonomija. Predikciona tržišta i obrazovne kategorije se izostavljaju.
   Filtri nisu potpuni: složena rečenica, navod ili nova formulacija mogu
   biti propušteni ili pogrešno protumačeni.
6. Tekstovi se grupišu po ekonomiji i oblasti. CPI i PPI zato mogu završiti
   u istoj oblasti inflacije; ovo nije precizno povezivanje jedinstvenih događaja.
   Broj članaka ne pojačava glas. Jedan prepoznati suprotan kanal daje
   „Suprotni uticaji u vijestima”; ne koristi se većinsko glasanje.
7. Ako je osnovni signal jasan, a vijesti imaju suprotan ili miješan uticaj,
   završni smjer je **Nema jasnog smjera**. Saglasne vijesti ne pojačavaju
   osnovni skor i ne pretvaraju neodređen osnovni signal u jasan. Bez
   prepoznatog smjera zadržava se osnovna procjena uz status pokrivenosti.

U JSON-u `outlooks` čuva osnovni model, `news_context` tumačenje vijesti,
a `combined_outlooks` završni smjer koji web i Telegram prikazuju. Osnovni
skor ostaje −4 do +4, zbog čega se, npr., +3 može prikazati uz neodređen
završni zaključak i objašnjenje neslaganja. Ni taj skor ni novinski kontekst
nisu vjerovatnoća. Za sedmicu i mjesec koristi se ista provjera vijesti;
različito trajanje njihovih efekata nije procijenjeno.

Geopolitički/kreditni rizik je upozorenje, bez automatskog znaka za USD.
Nedostupan feed je vidljiv; odsustvo prepoznatog signala ne znači odsustvo
važnih vijesti. Broj komentara nije nepristrasan uzorak tržišta. Dnevni RSS
presjek može propustiti članke objavljene između pokretanja. Ne obrađuju
se svi govori, vijesti ili revizije podataka. Nema plaćenog konsenzus feeda.

Tijela članaka služe samo za obradu u memoriji. Izvještaj čuva naslove,
linkove, atribuciju, datume i unaprijed definisana objašnjenja pravila,
bez ponovnog objavljivanja članaka. Ne koriste se privatni IBKR/GFIS podaci.

**Nije dokazano da ova dopuna poboljšava prognozu.** Za validaciju treba
sačuvati vremenski označene originalne procjene i porediti osnovni i
završni smjer sa stvarnim promjenama nakon 5 i 20 narednih ECB objava,
na dovoljno dugom novom uzorku, uključujući broj propuštenih procjena.
Naknadno testiranje na izmijenjenim člancima može unijeti informacije iz budućnosti.
Takva evaluacija nije urađena u ovoj verziji. Testovi provjeravaju rad koda.

Javni izvor komentara:
- https://www.interactivebrokers.com/campus/traders-insight/?feed=news

Ekonomski kontekst (ne validacija naših pravila):
- https://www.federalreserve.gov/econres/notes/feds-notes/monetary-policy-and-exchange-rates-during-the-global-tightening-20240510.html

Navedena Fed studija razmatra očekivanja kamata i sklonost riziku i pokazuje
da sama razlika kamata ograničeno objašnjava kurs. Naš parser ne reprodukuje
njen model, podatke ili utvrđenu statistiku.
