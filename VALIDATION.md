# Provjera nadogradnje 0.3.0

Provjereno 15.10.2026. Osnova su postojeći fajlovi verzije 0.2.
Prije izmjene su build_cloud.py, fx_report.py i notify_telegram.py upoređeni
sa javnom granom main repozitorijuma FalconMNE/usd-eur-analyzer; sadržaj je isti.

- 51 Python test: svi prošli. Uključuju dosadašnjih 35 i 16 provjera kalendara.
- ICS: ljetnje/zimsko vrijeme SAD i Evrope, UTC, datum bez satnice, prelomljeni
  redovi, otkazani i promijenjeni događaji, nepodržana ponavljanja.
- Nedostupan ili zastario izvor vidljiv je kao takav; ne postaje potvrda da
  nema događaja. Prekid svih kalendara ne mijenja postojeći rezultat modela.
- Stvarno javno učitavanje 2026-10-15T07:02:11.820005+00:00: svih sedam
  osnovnih izvora i svih pet kalendara dostupno. Kalendar je vratio 15 odabranih
  događaja za narednih 30 dana. Buduća dostupnost nije garantovana.
- JavaScript provjeren kroz Node VM za America/Los_Angeles i Europe/Podgorica:
  lokalizacija satnica, kalkulator, svjež izvještaj i upozorenje nakon 36 sati.
- Novi Telegram tekst pregledan bez slanja poruke iz razvojnog okruženja.
- fx_core.py, fx_analyzer.py i postojeći workflow nisu mijenjani. Kalendar
  ne dodaje glasove u procjenu smjera i ne uvodi brokerske naloge.

Nije izvršeno: objava ove verzije na korisnikov GitHub, GitHub-hosted test ove
nadogradnje ili slanje njenog novog Telegram teksta. Vizuelno renderovanje
na telefonu nije potvrđeno: Chromium nije bio dostupan u razvojnom okruženju.
Provjereni su generisani HTML i njegov JavaScript, ali ne mobilni screenshot.

Ovo su provjere rada programa, ne potvrda prognostičke tačnosti modela.
