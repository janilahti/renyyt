# Renyyt – tekninen dokumentaatio

Käyttäjän ohje on [README.md](README.md), endpointit kuvataan tiedostossa [API.md](API.md) ja testaus tiedostossa [TESTING.md](https://github.com/janilahti/renyyt/blob/main/TESTING.md).

## Asennus ja hakemistorakenne

Peruspalvelin käyttää Python 3.8+:aa ja standardikirjastoa. Node.js ja selain-/laadunvarmistustyökalut tarvitaan vain kehityksessä. Lähdekoodipuusta käynnistys onnistuu komennolla `python3 run.py` tai `PYTHONPATH=src python3 -m renyyt`.

```text
src/renyyt/          Python-paketti ja palvelin
web/                HTML, CSS, i18n.js, helpers.js, app.js, service-worker.js ja brändiresurssit
scripts/            Koonti, paketointi ja CI-tarkistukset
dist/               Generoitu tuotantokooste, ei versionhallintaan
tests/              Python-, frontend-, selain- ja kuvavertailut
deploy/             systemd-, nginx-, Caddy- ja Cloud Run -esimerkit
.github/            CI, julkaisu ja kehitysmallipohjat
```

Asennus virtuaaliympäristöön lähdekoodipuusta:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 scripts/build.py
python -m pip install .
renyyt --check
renyyt
```

Rakenna tuotantoresurssit ennen asennusta; pip-paketointi sisällyttää olemassa olevan `dist/`-koosteen. Python-moduulit asennetaan ympäristön `site-packages`-hakemistoon ja ajonaikaiset resurssit `share/renyyt`-hakemistoon. Myös `python -m renyyt` toimii asennetusta paketista. Kehityksessä voi käyttää `python -m pip install -e '.[dev]'`. `RENYYT_DATA_ROOT` yliajaa ajonaikaisten web- ja dokumenttiresurssien juuren; se ei ole pelkkä kirjoitettavan datan hakemisto.

## Asetukset ja käynnistyksen tarkistus

Kaikki tuetut ympäristömuuttujat on lueteltu [.env.example-tiedostossa](https://github.com/janilahti/renyyt/blob/main/.env.example). Kopioi se tarvittaessa `.env`:ksi ja ota käyttöön vain muutettavat asetukset. Renyyt etsii `.env`:n ensin lähdekoodijuuresta, sitten asetetusta datajuuresta ja lopuksi työhakemistosta; ensimmäinen löytyvä tiedosto luetaan. Prosessin ympäristömuuttujat voittavat tiedoston arvot. Vaihtoehtoinen tiedosto valitaan prosessin muuttujalla `RENYYT_ENV_FILE=/etc/renyyt/renyyt.env`.

Muoto on `NAME=VALUE`, välilyöntejä sisältävät arvot lainataan. Shell-muuttujalaajennuksia ei tehdä. `SOURCE_DATE_EPOCH` on koontityökalujen asetus; tavalliset `RENYYT_*`-asetukset vaikuttavat palvelimeen.

Keskeiset ryhmät:

- Verkko: `RENYYT_HOST=127.0.0.1`, `RENYYT_PORT` tai sen puuttuessa `PORT`, viimeisenä oletus 8787; `RENYYT_BASE_PATH`.
- Upstream: session/login/services-aikakatkaisut 10/15/20 sekuntia.
- Lokit: `RENYYT_LOG_LEVEL=INFO`, `RENYYT_LOG_FORMAT=text` tai `json`.
- HTTP: sallittujen Host-/Origin-arvojen listat, luotetut proxyt, rungon kokoraja ja asiakassoketin aikakatkaisu.
- Ominaisuudet: PWA oletuksena päällä; SMTP-palaute, muistutukset ja palvelinmuistivälimuisti oletuksena pois.
- Metadata: version oletus luetaan `VERSION`-tiedostosta; `RENYYT_VERSION`, `RENYYT_BUILD_TIME` ja `RENYYT_GIT_COMMIT` voivat yliajaa ajonaikaiset tiedot.

```bash
python3 scripts/build.py
python3 run.py --check
```

`--check` validoi asetukset, mahdollisen fixturen, muistutusasetukset ja tarvittavat runtime-tiedostot ilman HTTP-palvelimen käynnistystä. Virheellinen konfiguraatio tuottaa virheen ja poistumiskoodin 2.

### Fixture kehityksessä

```bash
RENYYT_FIXTURE_FILE=tests/fixtures/e2e-services.json python3 run.py
```

Fixture korvaa upstream-kutsut. Tiedosto voi olla palvelulista tai objekti, jossa on `services` ja valinnaisesti `customerNumbers`. Suhteellinen polku ratkaistaan datajuuresta. Älä käytä oikeita asiakastietoja repossa tai testeissä. UI:n **Näytä HTTP-kutsu** -dialogin JSON-tuonti käsittelee tiedoston vain selaimessa.

## Tuotantokooste ja HTTP-välimuisti

```bash
python3 scripts/build.py
```

Kooste luo `dist/index.html`:n, `dist/asset-manifest.json`:n, service workerin, brändiresurssit ja SHA-256-sisältöhashatut JS/CSS-tiedostot. Palvelin käyttää koostetta, kun manifesti, sisältöhashit, indexin viittaukset ja tuoreus suhteessa lähteisiin täsmäävät. Puuttuva `dist/` on normaali kehitystila. Osittainen tai vanhentunut `dist/` voi aiheuttaa kehitysresurssien käytön ja `/ready`-virheen; rakenna se silloin uudelleen.

- Sisältöhashatut tuotantoresurssit: `Cache-Control: public, max-age=31536000, immutable`.
- HTML, dokumentit ja kehitysresurssit: `no-cache`, ETag ja Last-Modified; ehdollinen pyyntö voi palauttaa 304:n.
- API, health, ready ja metriikat: `no-store`. `/version` käyttää `no-cache`-asetusta.

Tuotannon reverse proxy hoitaa yleensä gzip/Brotli-pakkauksen. Itsenäiseen käyttöön `python3 scripts/build.py --gzip` tekee rinnakkaiset `.gz`-representaatiot. Python ei pakkaa lennossa. Se käyttää riittävän tuoretta rinnakkaista tiedostoa vain `Accept-Encoding: gzip` -asiakkaille ja lisää `Content-Encoding: gzip` sekä `Vary: Accept-Encoding`. Pakkaamaton tiedosto palvellaan muille; pelkkä gzip-index ilman hyväksyttyä pakkausta tuottaa 406:n. Resurssit kartoitetaan käynnistyksessä.

## Reverse proxy ja peruspolku

Frontti päättelee näkyvän peruspolun selaimen URL:sta. Jos proxy **säilyttää** `/renyyt`-etuliitteen upstreamille, aseta `RENYYT_BASE_PATH=/renyyt`; jos se **riisuu** etuliitteen, jätä asetus tyhjäksi. `/renyyt` ohjataan 308:lla polkuun `/renyyt/`. Myös API-, dokumentti-, embed- ja terveystarkistusreitit käyttävät määritettyä etuliitettä.

Välitettyihin `X-Forwarded-Host`-, `X-Forwarded-Proto`-, `X-Forwarded-For`- ja `X-Request-ID`-otsakkeisiin luotetaan vain, jos TCP-lähde kuuluu `RENYYT_TRUSTED_PROXIES`-listaan (IP-osoitteet/CIDR:t). Käytä vain oikeita välittäjiä, älä kaikkia internetosoitteita. Asiakas-IP ratkaistaan X-Forwarded-For-ketjusta oikealta vasemmalle. Nginxin tulee välittää esimerkiksi:

```nginx
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Host $http_host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
```

Kaikki API:n POST-reitit tarkistavat Host-/Origin-säännöt. Jos Origin on mukana, oletus sallii vain ulkoisen scheme+host-yhdistelmän mukaisen arvon. Originia lähettämätön curl toimii edelleen. Tarvittaessa käytä eksplisiittisiä `RENYYT_ALLOWED_ORIGINS`- ja `RENYYT_ALLOWED_HOSTS`-listoja; epästandardi portti kuuluu arvoon.

Nginx- ja Caddy-esimerkit löytyvät [deploy-hakemistosta](https://github.com/janilahti/renyyt/tree/main/deploy). Esimerkit on sovitettava omaan hostiin, TLS:ään ja proxy-verkkoon. Pidä Python localhostissa tai yksityisessä verkossa ja rajaa tarvittaessa metriikat proxyssa valvontajärjestelmälle.

## Docker

```bash
docker build -t renyyt .
docker run --rm --read-only -p 127.0.0.1:8787:8787 renyyt
```

Peruskuva on `python:3.13-slim`. Kooste tehdään kuvan rakennuksessa, sovellus ajetaan ei-root-käyttäjällä ja `.pyc`-kirjoitukset on estetty. `RENYYT_PORT` voittaa `PORT`-arvon myös terveystarkistuksessa. `RENYYT_BASE_PATH` huomioidaan `/ready`-polussa. OCI-metatietoihin voi käyttää koontiargumentteja `RENYYT_VERSION`, `VCS_REF` ja `BUILD_DATE`; sovelluksen `/version`-metadata asetetaan erikseen vastaavilla `RENYYT_*`-ympäristömuuttujilla.

Peruskontti ei asenna push-extraa. Muistutuskäyttö vaatii push-riippuvuudet lisäävän oman kuvan sekä ei-root-käyttäjälle kirjoitettavan pysyvän hakemiston ja `RENYYT_REMINDERS_DB`-polun. Älä säilytä SQLitea kontin katoavalla levyllä. Dockerin ja proxyn ollessa eri verkoissa luotettu proxy asetetaan sen todellisen IP:n/CIDR:n mukaan.

## systemd

Lähdekoodi-/arkistoasennuksen esimerkit ovat [deploy/systemd-hakemistossa](https://github.com/janilahti/renyyt/tree/main/deploy/systemd). Ne olettavat sovelluksen `/opt/renyyt`:iin, Python-virtuaaliympäristön `/opt/renyyt/venv`:iin ja käyttäjän/ryhmän `renyyt`.

```bash
sudo useradd --system --home-dir /var/lib/renyyt --create-home renyyt
sudo python3 -m venv /opt/renyyt/venv
sudo /opt/renyyt/venv/bin/python -m pip install /opt/renyyt
```

Kopioi `.env.example` tiedostoksi `/etc/renyyt/renyyt.env`, muokkaa asetukset ja suojaa tiedosto (esimerkiksi `root:renyyt`, tila 0640). `EnvironmentFile` luetaan systemd:n kautta. Pidä `/opt/renyyt` ylläpitäjän hallussa; kokoa resurssit käyttöönoton aikana, ei palvelun oikeuksilla jokaisessa käynnistyksessä. HTTP-palvelu käynnistyy asennetulla `renyyt`-komennolla. `StateDirectory=renyyt` antaa muistutuksille kirjoitettavan `/var/lib/renyyt`-hakemiston ilman oikeutta muuttaa sovelluskoodia.

Muistutuksia varten asenna `/opt/renyyt/venv/bin/pip install '/opt/renyyt[push]'`, määritä tietokanta `/var/lib/renyyt/reminders.sqlite3`:ksi ja käytä joko sisäistä scheduleriä tai ulkoista timeria, älä molempia. Timerin kellonajat käyttävät koneen aikavyöhykettä; sovita ne muistutushetkiin. `Persistent=true` ajaa rästiin jääneen ajon koneen käynnistyttyä.

Palvelin tukee SIGTERM:iä ja Ctrl-C:tä. Se lopettaa uusien pyyntöjen vastaanoton ja odottaa käynnissä olevia pyyntösäikeitä. Systemd-esimerkin pysäytysraja on 40 sekuntia; mitoita se tarvittaessa upstream-/SMTP-aikakatkaisujen mukaan.

## Cloud Run ja useat instanssit

[Cloud Run -ohje](https://github.com/janilahti/renyyt/blob/main/deploy/cloud-run/README.md) käsittelee `PORT`-asetusta, lokeja ja pysyvyysrajoja. Rate limiter, muistivälimuisti ja metriikat ovat prosessikohtaisia. Nykyinen SQLite-store on tarkoitettu pysyvälle palvelimelle; jaettu monen instanssin/serverless-muistutuspalvelu vaatii uuden pysyvän store-adapterin. Sisäiseen scheduleriin ei voi luottaa, jos instanssi nukutetaan tai CPU pysäytetään.

## Käyttöliittymän asetukset ja upotus

Kielivalinnat ovat `fi`, `en`, `sv`, `uk`, `ar`, `fa`, `vi` ja `zh-Hans`. Localeja ovat mm. `ar-EG`, `fa-IR-u-ca-gregory`, `vi-VN` ja `zh-CN`. Arabia/persia ovat RTL-kieliä; tekniset arvot eristetään LTR-muotoon. Kielisanakirjat ovat yhdessä sisältöhashatussa `i18n.js`:ssä (noin 114 kB / gzip 29 kB). Ratkaisu pitää kielenvaihdon ja offline-käytön yksinkertaisena; laajennusohje on [TESTING.md](https://github.com/janilahti/renyyt/blob/main/TESTING.md)-tiedostossa.

Oma järjestys ja astiarajaukset tallennetaan selaimeen vakailla astia-avaimilla. Järjestely toimii vain normaalinäkymässä. Vähintään 900 pikselin ikkunassa nuolipainikkeet ovat lisätietojen avausten rinnalla ja piiloutuvat, kun jompikumpi osio on auki. Tiivis näkymä näyttää saman järjestyksen ilman säätimiä tai vetämistä.

Upotus avataan `/embed`-polulla. **Näytä HTTP-kutsu** muodostaa esimerkiksi:

```text
https://example.fi/renyyt/embed#theme=dark&lang=fi&credentials=v1....&view=v1....
```

Tuetut teemat ovat `system`, `light` ja `dark`. `credentials` on versionoitu, avaimen sisältävä AES-GCM-sumennettu tunnusblob, ei turvallinen salaus. Fragmenttia ei lähetetä GET-pyynnössä, mutta koko linkki sisältää palautettavan salasanan ja on salaisuus. Ilman blobia käytetään saman originin tallennettuja tunnuksia, jos niitä on.

`view` kuljettaa tehokkaat astiarajaukset, järjestystilan, oman järjestyksen ja tiiviin näkymän asetuksen myös ilman tunnuksia. Näin linkki ei tarvitse kohdeselaimen aiempia asetuksia. Asennetun PWA:n manifestin aloitusosoite on `/embed`; ilman `view`-blobia käytetään selaimen omia näkymäasetuksia.

## PWA, offline-data ja selaimen tallennus

`RENYYT_PWA_ENABLED=true` on oletus. Tuotannossa asennus ja service worker vaativat HTTPS:n; localhost kelpaa kehityksessä. Asennusprompti avataan vain käyttäjän toimesta. iOS/Safari näyttää aloitusnäytölle lisäämisen ohjeen.

Service worker tallentaa asennuksen yhteydessä sovelluskuoren juurisivun. Navigaatio yrittää verkkoa ja käyttää yhteysvirheessä tätä tallennettua kuorta; navigaatiovastauksia ei päivitetä aggressiivisesti runtime-cacheen. Saman originin script/style/image/manifest/font- ja Markdown-resurssit käyttävät network-first-välimuistia. API-, health-, ready-, version- ja metrics-vastauksia ei tallenneta service workerilla.

Frontti säilyttää erikseen `localStorage`ssa supistetun korttidatan, ei koko API-vastausta tai kimppaosakkaiden henkilötietorakenteita. Epäonnistuneen haun fallback merkitään vanhentuneeksi aikaleiman kanssa. Tunnusten tallennus on erillinen opt-in; jo korttidata ja omat asetukset voivat olla asiakaskohtaisia. `RENYYT_PWA_ENABLED=false` poistaa manifestin, service workerin ja asennus-UI:n sekä siivoaa aiemmat rekisteröinnit/sovelluskuoren cachet.

## Upstreamin kirjautumisketju

Oma jätehuollon rajapinta on dokumentoimaton selainpalvelu. Jokainen varsinainen haku luo cookie-istunnon:

1. `GET https://extranet.pjhoy.fi/pirkka/` alustaa session. HTML-vastaus on normaali.
2. `POST https://extranet.pjhoy.fi/pirkka/j_acegi_security_check?target=2` lähettää lomakekentät `j_username`, `j_password`, `remember-me=false`. Redirectit pysyvät odotetussa HTTPS-extranetissä. Kirjautumislomakkeen tunnisteet auttavat havaitsemaan epäonnistumisen; HTML:ää ei parsita sovellusdataksi.
3. `GET https://extranet.pjhoy.fi/pirkka/secure/get_services_by_customer_numbers.do?customerNumbers[]=...` hakee JSON-palvelulistan. Usealle asiakasnumerolle annetaan useita query-arvoja.

Paluu kirjautumissivulle tuottaa `AUTH_SESSION_FAILED`:n, muu odottamaton sisältö `UPSTREAM_INVALID_RESPONSE`:n, virheellinen JSON `UPSTREAM_INVALID_JSON`:n ja extranetin ulkopuolinen redirect `UPSTREAM_UNEXPECTED_REDIRECT`:n. Tuntemattomia kenttiä käsitellään sallivasti. Esimerkiksi `ASTNextDate`, `ASTVali`, `ASTNimi` ja `tariff.productgroup` ohjaavat korttien esitystä.

## HTTP- ja tietoturvarajat

CSP rajaa script/style-lähteet arvoon `'self'`; inline-JS/CSS:ää ei tarvita. Vastauksissa ovat `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` ja rajattu Permissions-Policy. Upotuksen vuoksi `X-Frame-Options`- ja `frame-ancestors`-rajoituksia ei aseteta automaattisesti.

POST vaatii JSON-sisältötyypin ja Content-Lengthin. API:n oletuskokoraja on 16384 tavua (`RENYYT_MAX_REQUEST_BODY`); palaute voi sallia suuremman rungon liitteensä takia. Asiakassoketin aikakatkaisu on 30 s. Liian suuri runko tuottaa 413:n, puuttuva pituus 411:n ja virheellinen sisältötyyppi 415:n. HEAD toimii GET-reiteillä; OPTIONS ilmoittaa sallitut metodit.

Epäonnistuneiden `AUTH_FAILED`-kirjautumisten IP-kohtainen raja on oletuksena 8 yritystä / 300 s, estoaika 600 s. Onnistunut kirjautuminen tyhjentää historian. Esto palauttaa 429:n ja Retry-Afterin. Asetukset ovat `RENYYT_RATE_LIMIT_ATTEMPTS`, `WINDOW`, `BLOCK`, `CLEANUP_INTERVAL` ja valinnainen `WHITELIST` (kaikissa etuliite `RENYYT_RATE_LIMIT_`).

## Lokit, metadata ja valvonta

INFO/DEBUG eivät kirjaa tunnuksia tai pyyntö-/vastausrunkoja. DEBUG sisältää upstream-vaiheet, statukset, sisältötyypit, koot ja kestot sekä tuntemattomien kenttien nimet ja rakennetyypit. TRACE on tarkoituksella arkaluonteinen poikkeus: API:n tunnukset ja onnistuneesti parsitut JSON-rungot sekä SMTP:n tunnukset, viestit ja protokollavastaukset voivat päätyä lokiin. Upstreamin HTML/JavaScript ei kuulu TRACEen. Käytä TRACEa vain lyhyesti, suojaa lokit ja poista ne käytön jälkeen. Ks. [turvallisuusohje](https://github.com/janilahti/renyyt/blob/main/SECURITY.md).

Jokaisella vastauksella on `X-Request-ID`, joka on myös lokissa. Vain luotetun proxyn kelvollinen tunniste hyväksytään.

- `/health`: prosessi vastaa; ei upstream-kirjautumisen tarkistus.
- `/ready`: runtime-resurssit, dokumentit, brändit, konfiguraatio ja mahdollinen tuotantomanifesti; virheessä 503. Ei Renyy-palvelun saatavuuslupaus.
- `/version`: versio, koontiaika, commit, API-versiot ja repository.
- `/metrics`: Prometheus text exposition 0.0.4, tai Accept-neuvottelulla OpenMetrics.
- `/metrics/openmetrics`: OpenMetrics 1.0, lopussa `# EOF`.

Metriikat kattavat mm. pyyntömäärät ja kestot, vastaustavut, readiness-tarkistukset, rate limiterin, välimuistin ja upstream-vaiheet. Tunnuksia tai asiakasdataa ei käytetä tunnisteina. Kaikki tilastot ovat prosessikohtaisia.

## Valinnainen palvelinmuistivälimuisti

Cache aktivoituu vain, jos sekä `RENYYT_CACHE_MAX_ENTRIES` että `RENYYT_CACHE_TTL_SECONDS` ovat yli nollan. `RENYYT_CACHE_MAX_BYTES` rajaa vastausdatan koon (oletus 16 MiB). Vain onnistuneet JSON-vastaukset tallennetaan prosessin RAM-muistiin; taustasiivous vanhentaa ne TTL:n mukaan ja täysi cache karsitaan LRU-periaatteella.

Avaimena on prosessikohtainen HMAC-SHA256 koko autentikoidusta pyynnöstä. Saman avaimen yhtäaikaiset cache-missit yhdistetään single-flight-lukolla, eri avaimet toimivat rinnakkain. Tunnuksia ei säilytetä selväkielisenä cache-avaimessa, mutta vastausdata on muistissa. Aiemmin hyväksytyt tunnukset voivat saada cached vastauksen TTL:n loppuun asti upstream-salasanan muutoksen jälkeenkin.

`X-Renyyt-Cache` on `HIT`, `MISS` tai `DISABLED`. Vastauksen `upstreamFetchedAt` säilyy ja `upstreamAgeSeconds` lasketaan jokaisella vastauksella uudelleen. Ks. [API.md](API.md).

## Valinnainen SMTP-palaute

Palaute aktivoituu, kun HOST, FROM ja TO ovat asetettuina (`RENYYT_SMTP_*`); FROM käyttää USER-arvoa, jos omaa arvoa ei ole. USER edellyttää PASSWORDia. STARTTLS oletuksena true sopii yleensä portille 587, SSL portille 465; niitä ei voi käyttää yhtä aikaa. Salaisuudet eivät kuulu konttikuvaan tai versionhallintaan.

Gmail-esimerkki: `smtp.gmail.com:587`, STARTTLS ja sovellussalasana. SMTP-timeout on oletuksena 10 s, palauteraja 5 viestiä / 600 s per IP. Viesti on enintään 4000 merkkiä. Vapaaehtoinen turvallisen muotoinen sähköpostiosoite asetetaan Reply-To:ksi; muu vastausosoite jää tekstiosaan. Käyttäjän erikseen valitsema JSON-liite voi sisältää asiakaskohtaisia tietoja; oletuskokoraja on 262144 tavua (`RENYYT_FEEDBACK_MAX_DATA_BYTES`). Sovellus ei lisää salasanaa liitteeseen, eikä liitettä tallenneta levylle. SMTP-aikakatkaisu tuottaa `FEEDBACK_SMTP_TIMEOUT`:n (504).

## Valinnaiset Web Push -muistutukset

Asenna lähdekoodista `python -m pip install '.[push]'` tai julkaistusta paketista `pip install 'renyyt[push]'`. Python 3.8/3.9 käyttää pywebpush 1.14.1:tä, Python 3.10+ versiota >=2.5,<3. Perusasennus ei tarvitse näitä riippuvuuksia.

```bash
renyyt reminders generate-vapid
```

Komento tulostaa private/public-avaimet `.env`-muodossa. Säilytä private-avain salaisena ja määritä:

```dotenv
RENYYT_REMINDERS_ENABLED=true
RENYYT_REMINDERS_DB=/var/lib/renyyt/reminders.sqlite3
RENYYT_VAPID_PRIVATE_KEY=<private-key>
RENYYT_VAPID_PUBLIC_KEY=<public-key>
RENYYT_VAPID_SUBJECT=mailto:admin@example.com
RENYYT_PUSH_TTL=86400
```

Tietokannan oletus on asetetun `RENYYT_DATA_ROOT`-hakemiston `reminders.sqlite3`, muuten `~/.local/share/renyyt/reminders.sqlite3`. Suhteellinen eksplisiittinen DB-polku ratkaistaan datajuuresta. Tietokanta, WAL/SHM-tiedostot ja varmuuskopiot ovat yksityistä runtime-dataa.

Store sisältää push-endpointin, subscription-avaimet, UI-kielen, tyhjennyspäivän, nimen, UTC-lähetyshetken ja lähetystiedon. Renyy-tunnuksia tai upstream-cookieita ei tallenneta. Selain korvaa vielä lähettämättömät muistutukset jokaisen onnistuneen tyhjennyshaun jälkeen. Jo lähetettyä identtistä muistutusta ei synny uudelleen pelkällä synkronoinnilla.

Jatkuvan palvelimen sisäinen scheduler:

```dotenv
RENYYT_REMINDERS_INTERNAL_SCHEDULER=true
RENYYT_REMINDERS_RUN_TIMES=07:00,18:00
RENYYT_REMINDERS_TIMEZONE=Europe/Helsinki
```

Scheduler odottaa määritettyihin kellonaikoihin. `local` käyttää palvelimen aikavyöhykettä, UTC toimii kaikilla tuetuilla Python-versioilla; nimetyt IANA-vyöhykkeet vaativat Python 3.9+:n zoneinfon ja käyttöjärjestelmän aikavyöhykedatan.

Vaihtoehtoisesti jätä sisäinen scheduler pois ja aja `renyyt reminders run-due` ulkoisella timerilla/cronilla. `renyyt reminders stats` näyttää storen tilanteen. SQLite vaatii samalle levylle pääsyn molemmilta prosesseilta; satunnainen serverless-instanssi ei ole jaettu store.

Selain tarvitsee PWA:n, service workerin, HTTPS:n ja käyttäjän erikseen myöntämän ilmoitusluvan. Android/Chromium tukee Web Pushia; iOS/iPadOS edellyttää aloitusnäytölle lisättyä web-appia ja versiota 16.4+. Palvelin lähettää pushit viimeisimmän selainhaun snapshotista, eikä voi päivittää tyhjennyspäiviä itsenäisesti ilman upstream-tunnuksia. Periodic Background Sync ei korvaa pushia ja scheduleriä.

## Testaus, CI ja julkaisu

Komennot ja CI:n valintataulukko ovat [TESTING.md](https://github.com/janilahti/renyyt/blob/main/TESTING.md)-tiedostossa. Python-versiot ovat 3.8/3.13, Node.js 24 ja runner Ubuntu 24.04. Markdown-muutokset saavat kevyen dokumentti-/koontitarkistuksen; koodi-, workflow- ja asetustiedostot ajavat kattavamman CI:n. Manuaalinen workflow_dispatch pakottaa koko sarjan.

```bash
SOURCE_DATE_EPOCH=1700000000 python3 scripts/build.py
SOURCE_DATE_EPOCH=1700000000 python3 scripts/package.py
python3 scripts/check_reproducible.py
```

`SOURCE_DATE_EPOCH` vakioi aikaleimat; reproducibility-tarkistus vertaa arkistoa ja wheeliä kahdesta erillisestä koonnista. Arkisto on `renyyt-<VERSION>.tar.gz` ja sisältää ylimmän `renyyt/`-hakemiston. Generoidut `.gz`-tiedostot, ympäristösalaisuudet, SQLite-runtime-data ja kehitysvälimuistit jätetään pois. Säilytä muukin yksityinen testidata ja avaintiedostot lähdepuun ulkopuolella: ignore-lista ei tunnista kaikkea mahdollista salaisuutta.

`release.yml` julkaisee lähdearkiston `v*`-tagille, kun tagi vastaa VERSIONia ja sen Python/frontend/build-tarkistukset läpäisevät. Se ei korvaa täyttä CI:tä. Varmista täysi vihreä CI julkaistavalle commitille **ennen** tagia; noudata [julkaisutarkistuslistaa](https://github.com/janilahti/renyyt/blob/main/.github/release-checklist.md). Ylläpitomuutokset eivät automaattisesti nosta versiota. Käytä vain patch-korotuksia nykyisen projektipäätöksen mukaisesti.

[AGENTS.md](https://github.com/janilahti/renyyt/blob/main/AGENTS.md) on kanoninen kehitysohje, ja [ROADMAP.md](https://github.com/janilahti/renyyt/blob/main/ROADMAP.md) kertoo valmistuneet laatutasot ja seuraavat selvitykset. Tällä hetkellä julkaistaan lähdearkisto/Python-paketti; natiiveja OS-asentimia ei vielä ole.
