# Renyyt – tekninen dokumentaatio

Tämä tiedosto sisältää Renyyt-palvelimen ajamiseen, kehittämiseen, testaamiseen, rakentamiseen, observabilityyn ja tuotantokäyttöön liittyvät yksityiskohdat. Yleisesittely ja käyttäjän kannalta olennaiset asiat ovat tiedostossa [README.md](README.md).

- Projektin julkinen repository: <https://github.com/janilahti/renyyt>
- Renyyn (Pirkanmaan Jätehuolto) virallinen sivusto: <https://renyy.fi/>
- Oma jätehuolto -palvelu: <https://renyy.fi/palvelut/oma-jatehuolto/>

## Hakemistorakenne

```text
.
├── README.md / TECHNICAL.md / API.md / CHANGELOG.md / VERSION / LICENSE
├── run.py
├── src/renyyt/          # Python-palvelin ja vastuupohjaiset moduulit
├── web/                # Kehitysversion HTML/CSS/JavaScript
├── scripts/            # Koonti- ja julkaisupaketointiskriptit
├── dist/               # Generoitu tuotantobuild (gitignore)
├── tests/              # Python- ja käyttöliittymätestit
├── deploy/systemd/     # systemd-palveluesimerkki
└── .github/workflows/  # CI ja tagirelease
```

`dist/` on generoitu hakemisto eikä kuulu normaalisti versionhallintaan. Julkaisupakettiin sen voi muodostaa komennolla `python3 scripts/build.py`.


## Python-paketointi

Projekti on standardi `src/`-rakenteinen Python-paketti eikä sillä ole ajonaikaisia ulkoisia Python-riippuvuuksia. Repo-hakemistosta palvelimen voi edelleen käynnistää yksinkertaisesti:

```bash
python3 run.py
```

Vaihtoehtoisesti lähdekoodipuusta:

```bash
PYTHONPATH=src python3 -m renyyt
```

Projektin voi asentaa tavalliseen Python-ympäristöön tai virtuaaliympäristöön:

```bash
python3 -m pip install .
renyyt
```

Asennuksessa Python-moduulit menevät ympäristön `site-packages`-hakemistoon ja ajonaikaiset web-resurssit sekä README/VERSION/CHANGELOG asennetaan ympäristön `share/renyyt`-hakemistoon. `python -m renyyt` toimii myös asennetusta paketista. Kehityskäyttöön voi käyttää editable-asennusta `python3 -m pip install -e .`. `RENYYT_DATA_ROOT`-ympäristömuuttujalla ajonaikaisten resurssien juurihakemiston voi tarvittaessa yliajaa.

## Käynnistys

Tarvitset vain Python 3:n.

```bash
git clone https://github.com/janilahti/renyyt.git renyyt
cd renyyt
python3 run.py
```

Avaa selaimessa:

```text
http://127.0.0.1:8787
```


## README selaimessa

Sovellus tarjoaa tämän tiedoston raakamuotoisena osoitteesta `/README.md`. Käyttöliittymän **README**-painike hakee tiedoston ja muotoilee yleisimmät Markdown-rakenteet (otsikot, listat, koodilohkot, inline-koodin, lihavoinnit ja HTTP(S)-linkit) ilman ulkoisia kirjastoja tai CDN-riippuvuuksia.

Tavallinen selain ei yleensä muotoilee `.md`-tiedostoa itsestään muotoilluksi dokumentiksi, vaan näyttää sen tekstinä. Siksi muotoilu tehdään tässä sovelluksen omalla JavaScriptillä.

## Oma jätehuolto -upstreamin kirjautumis- ja datanhakuketju

Renyyt ei käytä erillistä julkista JSON-API:a, johon voisi tehdä yhden autentikoidun HTTP-pyynnön. Pirkanmaan Jätehuollon Oma jätehuolto -toiminto on osa selaimelle tarkoitettua extranet-sovellusta, joten Renyyt muodostaa saman cookie-pohjaisen istunnon kuin selain ja käyttää vasta sen jälkeen sovelluksen sisäistä JSON-endpointia. Tämä selittää, miksi upstream-liikenteessä näkyy normaalisti myös HTML-vastauksia.

Yksi tyhjennystietojen haku etenee näin:

1. **Istunnon alustus**

   ```http
   GET https://extranet.pjhoy.fi/pirkka/
   ```

   Vastauksena odotetaan normaalisti HTML-sivua. Sisältöä ei parsita sovellusdataksi; pyynnön tarkoitus on alustaa upstream-istunto ja kerätä `CookieJar`iin palvelimen asettamat evästeet. DEBUG-lokiin kirjataan vain teknisiä metatietoja, kuten status, sisältötyyppi, koko ja kesto.

2. **Kirjautuminen**

   ```http
   POST https://extranet.pjhoy.fi/pirkka/j_acegi_security_check?target=2
   Content-Type: application/x-www-form-urlencoded
   ```

   Lomakerungossa lähetetään `j_username`, `j_password` ja `remember-me=false`. `urllib` seuraa redirectit saman cookie-istunnon sisällä. Onnistunut kirjautuminen johtaa tavallisesti suojattuun `/pirkka/secure/`-näkymään, jonka vastaus voi jälleen olla HTML:ää.

   Kirjautumista ei päätellä enää pelkästään `login_error`-tekstistä. Renyyt tarkistaa myös, että redirectin lopullinen URL pysyy odotetussa HTTPS-extranetissä, ja tunnistaa kirjautumissivun muutamien vakaiden lomaketunnisteiden (`j_username`, `j_password`, `j_acegi_security_check`) perusteella. Odottamaton redirect extranetin ulkopuolelle hylätään. HTML:n tarkkaan DOM-rakenteeseen ei kuitenkaan sitouduta, jotta upstreamin ulkoasumuutokset eivät tarpeettomasti riko kirjautumista.

3. **Varsinainen JSON-datan haku**

   ```http
   GET https://extranet.pjhoy.fi/pirkka/secure/get_services_by_customer_numbers.do?customerNumbers[]=...
   ```

   Useita asiakasnumeroita varten queryssa on useita `customerNumbers[]`-parametreja. Tämän pyynnön pitää palauttaa JSONia. Renyyt tarkistaa lopullisen redirect-URL:n, tunnistaa mahdollisen paluun kirjautumissivulle sessiovirheeksi, vaatii JSON-sisältötyypin, parsii rungon JSONiksi ja validoi, että ylimmän tason rakenne on palvelulista. Tuntemattomia kenttiä käsitellään sallivasti, jotta upstream voi lisätä uusia kenttiä rikkomatta sovellusta.

Jos services-pyyntö redirecttaa takaisin kirjautumiseen tai palauttaa kirjautumissivun, tuloksena on `AUTH_SESSION_FAILED`. Jos vastaus ei ole JSONia eikä näytä kirjautumissivulta, kyse on `UPSTREAM_INVALID_RESPONSE`-virheestä. JSONiksi ilmoitettu mutta syntaktisesti virheellinen sisältö tuottaa `UPSTREAM_INVALID_JSON`-virheen. Odottamattomat redirectit PJH:n extranetin ulkopuolelle tuottavat `UPSTREAM_UNEXPECTED_REDIRECT`-virheen.

TRACE-lokitus on tarkoituksella rajattu tähän ketjuun niin, että vain onnistuneesti parsittu varsinainen JSON-liikenne voidaan kirjata sisältöineen. Istunto- ja kirjautumisvaiheiden HTML-, JavaScript- tai muu web-sisältö ei kuulu TRACE-lokiin. Tämä on tärkeää sekä lokimelun että sen vuoksi, ettei upstream-sivujen koko sisältöä kopioida tarpeettomasti diagnostiikkalokeihin.

Toteutus on siis tarkoituksella kolmivaiheinen eikä yksi “siisti” API-kutsu: JSON-endpoint toimii olemassa olevan selainistunnon sisällä ja riippuu sitä edeltävästä kirjautumisesta sekä evästeistä. Jos Pirkanmaan Jätehuolto muuttaa kirjautumis- tai endpoint-rakennetta, Renyytin upstream-sovitin voi vaatia päivityksen.

## HTTP-välimuisti ja gzip

Palvelin käyttää seuraavia välimuistiotsakkeita:

- `index.html`, `/embed`, `styles.css` ja `app.js`: `Cache-Control: no-cache`
- `README.md` ja `/version`: `Cache-Control: no-cache`
- `/api/v1/renyyt`: `Cache-Control: no-store`
- `/health`, `/ready` ja `/metrics`: `Cache-Control: no-store`

Palvelin tukee valmiiksi pakattuja gzip-representaatioita kaikille tarjoilemilleen tekstimuotoisille staattisille resursseille. Jos esimerkiksi `styles.css.gz`, `app.js.gz` tai tuotannon sisältöhashatun resurssin rinnalla oleva `.gz`-tiedosto löytyy, on vähintään yhtä uusi kuin pakkaamaton tiedosto ja asiakasohjelma ilmoittaa `Accept-Encoding: gzip`, palvelin lähettää valmiin `.gz`-version. URL pysyy alkuperäisenä `.css`/`.js`/`.html`-osoitteena ja vastaukseen lisätään `Content-Encoding: gzip` sekä `Vary: Accept-Encoding`. Python ei pakkaa sisältöä lennossa.

Tuotantokoosteen HTML:n ja kaikkien hashattujen JS/CSS-assettien gzip-versiot voi tehdä yhdellä komennolla:

```bash
python3 scripts/build.py --gzip
```

Kehitystiedostolle voi halutessaan tehdä rinnakkaisen gzip-version myös käsin, esimerkiksi `gzip -9 -c web/app.js > web/app.js.gz`. Palvelin kartoittaa käyttökelpoiset valmiiksi pakatut resurssit käynnistyessään.

## Service worker ja selainvälimuisti

`RENYYT_PWA_ENABLED=true` on oletus. Kun asetus on `false`, palvelin poistaa manifest-linkin HTML:stä eikä tarjoile manifestia tai service workeria; selainpuoli ei myöskään rekisteröi service workeria tai näytä asennus-UI:ta. PWA-tilassa `web/service-worker.js` tarjoillaan vakaasta `/service-worker.js`-reitistä. Se käyttää network-first-strategiaa sovelluskuoren HTML/CSS/JavaScript/kuville: onnistunut verkkovastaus päivittää Cache Storagen ja yhteysvirheessä käytetään viimeksi tallennettua kopiota. API-, health-, ready-, version- ja metrics-vastauksia service worker ei tallenna.

Tyhjennysdataa ei tallenneta service workerin HTTP-cacheen. Frontend tallentaa erikseen `localStorage`en supistetun, henkilötietoja minimoivan korttidatan onnistuneen haun jälkeen. Koko raakaa API-vastausta ei tallenneta offline-käyttöä varten.

Tuotantobuild kopioi service workerin `dist/service-worker.js`:ksi ja tallentaa sen SHA-256-hashin `asset-manifest.json`:iin. Readiness/build-validointi tarkistaa myös tämän tiedoston.

## Käänteinen välityspalvelin ja peruspolku

Käyttöliittymä tunnistaa selaimessa näkyvän peruspolun automaattisesti. Sovellus voi siis näkyä esimerkiksi osoitteessa:

```text
https://example.fi/renyyt/
```

Jos käänteinen välityspalvelin **riisuu** `/renyyt`-etuliitteen ennen pyynnön välittämistä Pythonille, palvelin voidaan käynnistää normaalisti ilman lisäasetuksia.

Jos käänteinen välityspalvelin **säilyttää** etuliitteen taustapalvelupyynnössä, käynnistä palvelin näin:

```bash
RENYYT_BASE_PATH=/renyyt python3 run.py
```

Tällöin palvelin hyväksyy muun muassa polut `/renyyt/`, `/renyyt/embed`, `/renyyt/styles.css`, `/renyyt/app.js`, `/renyyt/README.md`, `/renyyt/health`, `/renyyt/ready`, `/renyyt/version`, `/renyyt/metrics`, `/renyyt/CHANGELOG.md` ja `/renyyt/api/v1/renyyt`. Pyyntö `/renyyt` ilman loppukauttaviivaa ohjataan HTTP 308 -vastauksella osoitteeseen `/renyyt/`, jotta suhteelliset staattiset resurssit ratkeavat oikein.

Käyttöliittymän README-, API-, curl- ja embed-URL:t muodostetaan näkyvän selaimen URL:n pohjalta, joten ne säilyttävät peruspolun automaattisesti.

### Gzip käänteisen välityspalvelimen kanssa

Python käyttää rinnakkaisia `.gz`-tiedostoja vain, jos asiakasohjelma ilmoittaa `Accept-Encoding`-otsakkeessa tukevansa gzipia. Jos pakkaamaton tiedosto löytyy, se palvellaan asiakasohjelmalle, joka ei hyväksy gzipia. Jos vain gzipattu index löytyy, asiakasohjelmalle palautetaan `406 Not Acceptable`, jos pakkaamatonta indexiä ei ole eikä asiakasohjelma hyväksy gzipia.

Jos käänteinen välityspalvelin (esimerkiksi nginx tai Caddy) hoitaa pakkauksen, jätä `scripts/build.py --gzip` ajamatta ja käytä tavallista `python3 scripts/build.py` -koontia. Tällöin Python lähettää pakkaamattomat resurssit välityspalvelimelle, joka voi hoitaa gzip/Brotli-pakkauksen ulospäin. Tämä on suositeltu tuotantomalli käänteisen välityspalvelimen takana.

## Selainturva ja upotus

Palvelin lisää vastauksiin perustason turvaotsakkeet: `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` ja tarpeettomia selainominaisuuksia rajoittavan `Permissions-Policy`-otsakkeen. CSS ja JavaScript ovat omissa tiedostoissaan, joten CSP:n `script-src` ja `style-src` on rajattu arvoon `'self'` ilman `unsafe-inline`-poikkeusta. Sovelluksen embed-käyttö on tarkoituksellinen, joten palvelin ei lähetä `X-Frame-Options`-otsaketta eikä CSP:n `frame-ancestors`-rajoitusta.

## HTTP-välimuisti ja ehdolliset pyynnöt

Staattiset tiedostot käyttävät `Cache-Control: no-cache` -otsaketta sekä `ETag`- ja
`Last-Modified`-validaattoreita. Selain voi siis säilyttää paikallisen kopion, mutta
varmistaa sen tuoreuden serveriltä. Muuttumattomaan `index.html`-, `styles.css`-, `app.js`- tai `README.md`-
tiedostoon palvelin voi vastata kevyellä `304 Not Modified` -vastauksella.

Käyttäjäkohtaiset `/api/v1/renyyt`-vastaukset sekä `/health` ja `/ready` käyttävät edelleen
`Cache-Control: no-store` -asetusta.

## Renyy-yhteyden aikakatkaisut

Upstream-kutsujen timeoutit ovat eksplisiittiset ja niitä voi tarvittaessa säätää
environment-muuttujilla (sekunteina):

```bash
RENYYT_SESSION_TIMEOUT=10 \
RENYYT_LOGIN_TIMEOUT=15 \
RENYYT_SERVICES_TIMEOUT=20 \
python3 run.py
```

Virhevastauksissa on ihmiselle tarkoitetun `error`-tekstin lisäksi koneellisesti
luettava `code`, esimerkiksi `AUTH_FAILED`, `UPSTREAM_TIMEOUT` tai
`UPSTREAM_INVALID_JSON`. Palvelimen virheloki ei tulosta asiakasnumeroa, salasanaa
tai Renyyn palauttamaa asiakasdataa.

## Testit

Koko testaus- ja CI-komentojen koonti on tiedostossa [TESTING.md](TESTING.md). Alla säilytetään myös testaukseen liittyvä tekninen tausta osana muuta käyttö- ja kehitysdokumentaatiota.


Palvelimen perustoiminnot voi tarkistaa Pythonin omalla `unittest`-moduulilla ilman
lisäriippuvuuksia:

```bash
PYTHONPATH=src python3 -m unittest -v tests.test_server
```

Testit kattavat mm. peruspolku -reitityksen, gzip-neuvottelun, välimuisti-headerit,
ETag/304-käytöksen, käyttöliittymäresurssit, README-/health-/ready-/version-/metrics-reitit, tiukan CSP:n, Origin/Host-suojan, konfiguraation, pyyntötunnisteen sekä taustapalvelu-virhepolut ja Renyyn datan keskeiset skeemareunatapaukset.

## HTTP HEAD -tuki

Palvelin tukee `HEAD`-pyyntöjä reiteille `/`, `/index.html`, `/embed`, `/styles.css`, `/i18n.js`, `/helpers.js`, `/app.js`, hashatuille `/assets/...`-resursseille, `/README.md`, `/health`, `/ready`, `/version`, `/api/v1/features`, `/metrics` ja `/metrics/openmetrics` (sekä vastaaville `RENYYT_BASE_PATH`-prefiksoiduille reiteille). HEAD palauttaa samat olennaiset otsakkeet ja `Content-Length`-arvon kuin GET, mutta ei vastausrunkoa. Staattisten resurssien ehdolliset `ETag`/`Last-Modified`-pyynnöt toimivat myös HEADilla.

## Päivitystila

Tyhjennysnäkymä näyttää viimeisimmän onnistuneen haun ajan ja seuraavan automaattisen haun ajan. Jos automaattipäivitys epäonnistuu, aiemmin haetut tiedot jätetään näkyviin ja metarivillä kerrotaan päivitysvirheestä sekä seuraavasta yrityksestä.


## Palvelimen konfiguraatio

Palvelimen keskeiset asetukset ovat ympäristömuuttujia. Projektin juuressa oleva `.env.example` sisältää kaikki tuetut asetukset kommentoituina oletusarvoineen. Sen voi kopioida nimelle `.env`; Renyyt lukee tiedoston automaattisesti eikä ylikirjoita prosessille jo asetettuja ympäristömuuttujia. Vaihtoehtoisen tiedoston voi valita prosessin ympäristömuuttujalla `RENYYT_ENV_FILE=/polku/tiedostoon`. Välilyöntejä sisältävät arvot kannattaa kirjoittaa lainausmerkkeihin, esimerkiksi `RENYYT_BUILD_TIME="2026-10-04 14:30:00 +0300"`. `.env`-lukija ei tee shell-muuttujalaajennuksia. Oletusarvot sopivat paikalliseen käyttöön:

```text
RENYYT_HOST=127.0.0.1
RENYYT_PORT=8787
RENYYT_BASE_PATH=
RENYYT_SESSION_TIMEOUT=10
RENYYT_LOGIN_TIMEOUT=15
RENYYT_SERVICES_TIMEOUT=20
RENYYT_LOG_LEVEL=INFO
RENYYT_LOG_FORMAT=text
RENYYT_VERSION=dev
RENYYT_BUILD_TIME=
RENYYT_GIT_COMMIT=
RENYYT_ALLOWED_ORIGINS=
RENYYT_ALLOWED_HOSTS=
RENYYT_TRUSTED_PROXIES=
RENYYT_MAX_REQUEST_BODY=16384
RENYYT_CLIENT_SOCKET_TIMEOUT=30
RENYYT_RATE_LIMIT_ATTEMPTS=8
RENYYT_RATE_LIMIT_WINDOW=300
RENYYT_RATE_LIMIT_BLOCK=600
RENYYT_RATE_LIMIT_CLEANUP_INTERVAL=300
RENYYT_RATE_LIMIT_WHITELIST=
RENYYT_SMTP_HOST=
RENYYT_SMTP_PORT=587
RENYYT_SMTP_USER=
RENYYT_SMTP_PASSWORD=
RENYYT_SMTP_FROM=
RENYYT_SMTP_TO=
RENYYT_SMTP_STARTTLS=true
RENYYT_SMTP_SSL=false
RENYYT_SMTP_TIMEOUT=10
RENYYT_FEEDBACK_RATE_LIMIT=5
RENYYT_FEEDBACK_RATE_WINDOW=600
RENYYT_CACHE_MAX_ENTRIES=0
RENYYT_CACHE_TTL_SECONDS=0
RENYYT_CACHE_MAX_BYTES=16777216
```


### Fixture-data kehitys- ja E2E-testaukseen

`RENYYT_FIXTURE_FILE` voidaan asettaa JSON-tiedostoon, jolloin `/api/v1/renyyt` ei ota yhteyttä Oma jätehuolto -palveluun vaan käyttää tiedoston dataa. Tämä on tarkoitettu vain kehitykseen, vikojen toistamiseen ja automatisoituihin E2E-testeihin. Tiedosto voi sisältää joko suoran `services`-taulukon tai Renyyt-API:n vastauksen muotoisen objektin, jossa on vähintään `services`-taulukko ja valinnaisesti `customerNumbers`. Suhteellinen polku ratkaistaan Renyytin datajuuresta. `renyyt --check` validoi asetetun fixture-tiedoston ennen palvelimen käynnistystä. Playwright-testit käyttävät tätä mekanismia, joten selain-, HTTP-palvelin- ja renderöintipolku testataan oikeasti ilman ulkoista upstream-riippuvuutta.

`RENYYT_LOG_LEVEL` hyväksyy arvot `TRACE`, `DEBUG`, `INFO`, `WARNING` ja `ERROR`. `TRACE` on tarkoituksella arkaluonteinen diagnostiikkataso: se voi kirjata Renyy-kirjautumistunnukset, salasanat, asiakasnumerot, SMTP-tunnukset, palautteen sisällön sekä upstream- ja SMTP-vastauksia. TRACEa saa käyttää vain lyhytaikaiseen vianetsintään ympäristössä, jossa lokit voidaan suojata ja poistaa käytön jälkeen. `RENYYT_LOG_FORMAT` hyväksyy arvot `text` ja `json`; JSON-muoto sopii esimerkiksi Loki-/ELK-/journald-jatkokäsittelyyn. `RENYYT_VERSION`, `RENYYT_BUILD_TIME` ja `RENYYT_GIT_COMMIT` näkyvät `/version`-rajapintapolussa. `RENYYT_ALLOWED_ORIGINS` ja `RENYYT_ALLOWED_HOSTS` ovat pilkuilla eroteltavia sallittujen selain-Origin-arvojen ja Host-otsakkeiden listoja. `RENYYT_TRUSTED_PROXIES` on pilkuilla eroteltava lista luotettujen käänteisten välityspalvelinten IP-osoitteista tai CIDR-verkoista. `RENYYT_MAX_REQUEST_BODY` rajoittaa API:n POST-rungon koon, `RENYYT_CLIENT_SOCKET_TIMEOUT` hitaan asiakasyhteyden odotusajan ja `RENYYT_RATE_LIMIT_*` kirjautumisvirheisiin kohdistuvan brute force -suojauksen. `RENYYT_RATE_LIMIT_CLEANUP_INTERVAL` määrää vanhentuneiden muistissa pidettävien asiakasmerkintöjen siivousvälin. `RENYYT_RATE_LIMIT_WHITELIST` on valinnainen pilkuilla eroteltu IP/CIDR-lista, jolle autentikointivirheiden pyyntörajoitus ei ole käytössä. Virheellinen portti, aikakatkaisu, kokoraja tai lokitaso pysäyttää palvelimen heti käynnistyksessä selkeällä konfiguraatiovirheellä.

Palautetoiminto on oletuksena pois käytöstä. Se tulee käyttöliittymässä näkyviin, kun vähintään `RENYYT_SMTP_HOST`, `RENYYT_SMTP_FROM` ja `RENYYT_SMTP_TO` on asetettu. Jos `RENYYT_SMTP_USER` on asetettu, myös `RENYYT_SMTP_PASSWORD` vaaditaan. `RENYYT_SMTP_STARTTLS=true` sopii tavallisesti portille 587 ja `RENYYT_SMTP_SSL=true` portille 465; niitä ei voi käyttää samanaikaisesti. Gmailissa käytä esimerkiksi `smtp.gmail.com`, porttia 587, STARTTLS:ää ja Google-tilin App Password -salasanaa. SMTP-salasana pysyy vain palvelimen ympäristömuuttujassa eikä sitä lähetetä selaimelle. Palautepolulla on lisäksi IP-kohtainen oletusraja 5 viestiä 600 sekunnissa. Käyttäjä voi halutessaan liittää UI:ssa parhaillaan näkyvät tyhjennystiedot palautteeseen JSON-tiedostona; liitteen oletusraja on 262144 tavua (`RENYYT_FEEDBACK_MAX_DATA_BYTES`). `RENYYT_LOG_LEVEL=DEBUG` kirjaa SMTP-lähetyksen vaiheet (yhteyden muodostus, EHLO, STARTTLS, autentikointi ja lähetys), SMTP-vastauskoodit sekä kestot, mutta ei SMTP-salasanaa, viestin sisältöä eikä vastausosoitetta. `RENYYT_LOG_LEVEL=TRACE` kirjaa lisäksi tarkoituksellisesti SMTP-tunnukset, vastaanottaja-/Reply-To-tiedot, viestin sisällön ja SMTP-palvelimen vastaukset. SMTP-aikakatkaisu palautetaan erillisenä `FEEDBACK_SMTP_TIMEOUT`-virheenä (HTTP 504) eikä selaimen pyyntöaikakatkaisuna.


API-vastausten palvelinmuistivälimuisti on oletuksena pois käytöstä. Se aktivoituu vain, kun sekä `RENYYT_CACHE_MAX_ENTRIES` että `RENYYT_CACHE_TTL_SECONDS` ovat suurempia kuin nolla. Avaimena käytetään prosessikohtaisella satunnaisavaimella muodostettua HMAC-SHA256-tiivistettä asiakasnumerosta, salasanasta ja pyydetyistä asiakasnumerolisistä; tunnuksia ei säilytetä cache-avaimessa selväkielisinä. Vain onnistuneet lopulliset JSON-vastaukset tallennetaan. `RENYYT_CACHE_MAX_ENTRIES` rajaa LRU-periaatteella säilytettävien vastausten määrän, `RENYYT_CACHE_TTL_SECONDS` niiden enimmäisiän ja `RENYYT_CACHE_MAX_BYTES` koko välimuistin vastausdatan yhteenlasketun koon (oletus 16 MiB). Taustasiivooja poistaa vanhentuneet merkinnät myös silloin, kun uusia pyyntöjä tulee harvoin. Samalle cache-avaimelle osuvat yhtäaikaiset cache-missit yhdistetään avainkohtaisella single-flight-lukituksella: vain yksi pyyntö hakee upstreamista ja muut odottavat sen tulosta, mutta eri avaimet voivat edetä rinnakkain. Vastauksen `X-Renyyt-Cache`-otsake kertoo arvon `HIT`, `MISS` tai `DISABLED`. Välimuisti on vain prosessin RAM-muistissa eikä sitä kirjoiteta levylle. Koska cache-avain sisältää myös salasanan HMAC-muodossa, täsmälleen samoilla aiemmin toimineilla tunnuksilla voidaan saada cached vastaus TTL:n loppuun asti, vaikka upstream-tunnus olisi sillä välin vaihdettu tai poistettu käytöstä. Siksi TTL kannattaa pitää lyhyenä ympäristöissä, joissa tunnusten nopea mitätöinti on tärkeää.

`renyyt --check` tai lähdekoodipuussa `python3 run.py --check` validoi asetukset ja tarvittavat runtime-tiedostot käynnistämättä HTTP-palvelinta.


Esimerkiksi käänteisen välityspalvelimen kanssa:

```bash
RENYYT_HOST=127.0.0.1 \
RENYYT_PORT=8787 \
RENYYT_BASE_PATH=/renyyt \
RENYYT_LOG_LEVEL=INFO \
python3 run.py
```

## Lokitus ja pyyntötunniste

Jokainen HTTP-vastaus sisältää `X-Request-ID`-otsakkeen. Jos luotettu käänteinen välityspalvelin antaa kelvollisen `X-Request-ID`-arvon, palvelin säilyttää sen; muuten palvelin luo oman tunnisteen. Sama tunniste lisätään palvelimen pyyntö- ja virhelokeihin, mikä helpottaa yksittäisen pyynnön jäljittämistä.

Lokit eivät sisällä POST-runkoa, salasanaa, asiakasnumeroa tai Renyyn palauttamaa asiakasdataa. Upstream-virheestä voidaan kirjata turvallisesti virheluokka, paikallinen HTTP-status ja mahdollinen taustapalvelun HTTP-status.

## Terveys- ja valmiustarkistukset

`GET /health` kertoo vain, että HTTP-prosessi vastaa. `GET /ready` tarkistaa lisäksi, että sovelluksen käynnistyksessä havaitsema index-tiedosto sekä `styles.css`, `i18n.js`, `helpers.js`, `app.js`, `service-worker.js`, `README.md`, `API.md`, `VERSION` ja `CHANGELOG.md` ovat käytettävissä. Jos `dist/`-tuotantokooste on olemassa, myös asset-manifestin versio, asset-joukko, sisältöhashit ja tuotanto-indexin viittaukset validoidaan.

Valmis vastaus on esimerkiksi:

```json
{"status":"ready","checks":{"index":true,"styles":true,"javascript":true,"helpers":true,"productionBuild":true,"readme":true,"version":true,"changelog":true,"config":true}}
```

Jos välttämätön tiedosto puuttuu, `/ready` palauttaa HTTP 503:n. Readiness ei tee oikeaa kirjautumista Renyyn extranetiin eikä siten aiheuta taustapalvelu-kuormaa.

## Renyy-datan kevyt skeemavalidointi

Palvelin varmistaa ennen datan välittämistä selaimelle, että Renyyn vastaus on palvelulista ja että käyttöliittymän kannalta keskeiset kentät ovat odotetun tyyppisiä. Tarkistettavia kenttiä ovat esimerkiksi `ASTNextDate`, `ASTVali`, `ASTVali2`, `tariff.productgroup`, `kimppa` ja `KIRPros`.

Validointi on tarkoituksella salliva. Vain koko vastauksen väärä ylätason rakenne on kova `UPSTREAM_SCHEMA_ERROR`. Yksittäisen palvelun poikkeava päivämäärä tai kenttätyyppi välitetään edelleen raakadatan mukana ja ilmoitetaan `warnings`-listassa. Näin yhden palvelun muuttunut skeema ei estä muiden palveluiden näyttämistä. Tuntemattomat uudet kentät hyväksytään sellaisinaan. Käyttöliittymä eristää lisäksi jokaisen palvelukortin piirtämisen: yhden kortin näyttövirhe ei keskeytä muuta listaa.


## Versio- ja koontitiedot

`GET /version` palauttaa sovelluksen version ja valinnaiset koontitiedot JSON-muodossa. Oletusversio luetaan `VERSION`-tiedostosta; `RENYYT_VERSION` voi yliajaa sen käyttöönottoympäristössä. `RENYYT_BUILD_TIME` ja `RENYYT_GIT_COMMIT` ovat valinnaisia. `scripts/build.py` tallentaa saman julkaisuversion myös `asset-manifest.json`:iin. Julkaisumuutokset dokumentoidaan `CHANGELOG.md`:ssä, jonka palvelin tarjoaa myös reitistä `/CHANGELOG.md`. Esimerkiksi:

```json
{"version":"1.4.0","buildTime":"2026-10-01T20:00:00Z","gitCommit":"abc123"}
```

## Metriikat

`GET /metrics` palauttaa Prometheus-yhteensopivaa tekstimuotoista metriikkaa ilman lisäkirjastoja. Mukana ovat prosessin käyntiaika, koontitiedot, HTTP-pyyntömäärät, vastausrunkotavut, valmiustilan mittari, pyyntörajan hylkäykset, API-hakujen onnistumiset ja virheluokat, API-keston histogrammi sekä taustapalveluvaiheiden kutsumäärät, kestot ja viimeisimmät onnistumisajat. Metriikka ei sisällä asiakasnumeroita, salasanoja tai Renyyn asiakasdataa. Julkisessa asennuksessa `/metrics` kannattaa tarvittaessa rajata käänteisen välityspalvelimen ACL:llä vain valvontajärjestelmälle.

## API:n Origin- ja Host-suojaus

Selainpyynnöt `POST /api/v1/renyyt` -endpointtiin tarkistetaan CSRF-/cross-origin-riskin vähentämiseksi. Jos `Origin`-otsake on mukana, sen hostin pitää oletuksena vastata pyynnön `Host`-otsaketta. Komentoriviasiakkaat kuten `curl`, jotka eivät lähetä `Origin`-otsaketta, toimivat edelleen.

Käänteisen välityspalvelimen kannattaa säilyttää ulkoinen `Host`-otsake. Nginxissä esimerkiksi `välityspalvelin_set_header Host $http_host;`. Jos tämä ei sovi ympäristöön, sallitut arvot voi määritellä eksplisiittisesti:

```bash
RENYYT_ALLOWED_ORIGINS=https://example.fi,https://portal.example.fi \
RENYYT_ALLOWED_HOSTS=example.fi,portal.example.fi \
python3 run.py
```

`RENYYT_ALLOWED_ORIGINS` vertaa koko originia (scheme + host + mahdollinen portti). `RENYYT_ALLOWED_HOSTS` vertaa HTTP `Host` -otsaketta; jos käytössä on epästandardi portti, se kuuluu arvoon.

## Käyttöliittymän tiedostorakenne

Käyttöliittymä on jaettu viiteen lähdetiedostoon: `index.html`, `styles.css`, `i18n.js`, `helpers.js` ja `app.js`. Tällä hetkellä ne käyttävät `Cache-Control: no-cache` + ETag/Last-Modified -validointia, koska tiedostonimet eivät ole sisältöhashattuja. Jos myöhemmin otetaan käyttöön hashatut nimet kuten `app.a1b2c3.js`, niille voidaan antaa pitkä `max-age` + `immutable` -välimuisti.

## Tuotantokoonti ja sisältötunnisteiset resurssit

Kehitystiedostot pysyvät selkeillä nimillä `styles.css`, `i18n.js`, `helpers.js` ja `app.js`. Tuotantobuild ei tarvitse npm:ää tai muita lisäosia:

```bash
python3 scripts/build.py
```

Koonti luo `dist/assets/`-hakemistoon SHA-256-sisältöhashilla nimetyt tiedostot sekä `dist/index.html`-tiedoston ja `dist/asset-manifest.json`-manifestin. Esimerkiksi `app.js` voi muuttua nimeksi `assets/app.1a2b3c4d5e6f.js`.

Palvelin käyttää tuotantobuildia automaattisesti vain, jos manifesti, tuotanto-index ja kaikki sisältöhashatut resurssit löytyvät, sisältöhashit täsmäävät, tuotanto-index viittaa juuri manifestin assetteihin ja kooste on vähintään yhtä uusi kuin kehityslähteet. Jos `dist/` puuttuu kokonaan, kehitystiedostot ovat normaali varavaihtoehto. Jos osittainen tai rikkinäinen `dist/` löytyy, palvelin voi palvella kehitystiedostoja, mutta `/ready` ilmoittaa koontimanifestin virheestä HTTP 503:lla, jotta käyttöönotto-ongelma ei jää piiloon. Hashatut resurssit saavat otsakkeen:

```http
Cache-Control: public, max-age=31536000, immutable
```

HTML säilyy `no-cache`-tilassa. Koonti ei oletuksena tee gzip-tiedostoa, mikä sopii käänteisen välityspalvelimen taakse tehtävään asennukseen. Itsenäisessä käytössä gzip-versiot voi tehdä samalla:

```bash
python3 scripts/build.py --gzip
```

## Luotetun välityspalvelimen malli

Välitettyihin otsakkeisiin (`X-Forwarded-Host`, `X-Forwarded-Proto`, `X-Forwarded-For`) luotetaan vain, jos TCP-yhteyden lähdeosoite kuuluu `RENYYT_TRUSTED_PROXIES`-listaan. Lista hyväksyy yksittäisiä IP-osoitteita ja CIDR-verkkoja:

```bash
RENYYT_TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8 python3 run.py
```

Jos pyyntö ei tule luotetulta välityspalvelinlta, välitetyt otsakkeet jätetään huomiotta. Sama koskee välityspalvelinn antamaa `X-Request-ID`:tä. Tämä estää suoraa asiakasohjelmaa väärentämästä ulkoista hostia, protokollaa tai lokiin kirjattavaa asiakas-IP:tä.

TLS:n päättävän käänteisen välityspalvelimen kannattaa välittää vähintään:

```text
Host / X-Forwarded-Host: ulkoinen host
X-Forwarded-Proto: https
X-Forwarded-For: asiakkaan osoite
```

API:n oletus-Origin-tarkistus vertaa ulkoista scheme+host-yhdistelmää. `RENYYT_ALLOWED_ORIGINS` ja `RENYYT_ALLOWED_HOSTS` ovat edelleen käytettävissä ympäristöissä, joissa automaattinen vertailu ei sovi topologiaan.

## Prometheus ja OpenMetrics

`GET /metrics` säilyttää Prometheuksen perinteisen text exposition 0.0.4 -muodon. OpenMetrics 1.0 on saatavilla rinnalla kahdella tavalla:

```text
GET /metrics/openmetrics
```

Tai sisältöneuvottelulla:

```http
GET /metrics
Accept: application/openmetrics-text; version=1.0.0
```

OpenMetrics-vastauksen `Content-Type` on `application/openmetrics-text; version=1.0.0; charset=utf-8` ja vastaus päättyy `# EOF`-merkintään.

Metriikoissa ovat myös prosessin käynnistysaika ja käyntiaika, koonti- ja versiotiedot, aktiivisten HTTP-pyyntöjen määrä, kaikkien HTTP-reittien kestojen summa- ja lukumäärämittarit, vastausrungon tavumäärän summa- ja lukumäärämittarit, readiness sekä yksittäiset valmiustarkistukset, pyyntörajan hylkäykset, seurattujen ja estettyjen asiakkaiden määrät ja rajoittimen siivous- ja karsintalaskurit, taustapalvelun skeemavaroitukset, yhtenäiset API-tuloslaskurit, API-keston histogrammi sekä taustapalveluvaiheiden (`session`, `login`, `services`) kutsumäärät, yhteenlasketut kestot ja viimeisimmät onnistumisajat. Asiakasnumeroita, salasanoja tai Renyyn asiakasdataa ei käytetä metriikoiden tunnisteina.

## Kirjautumisyritysten rajoitus

API pitää muistissa epäonnistuneet `AUTH_FAILED`-kirjautumiset asiakas-IP-kohtaisesti. Oletuksena 8 epäonnistumista 5 minuutissa estää uudet kirjautumisyritykset 10 minuutiksi. Estetty pyyntö saa HTTP 429:n ja `Retry-After`-otsakkeen. Onnistunut kirjautuminen tyhjentää kyseisen asiakas-IP:n epäonnistumishistorian.

Asetukset:

```text
RENYYT_RATE_LIMIT_ATTEMPTS=8
RENYYT_RATE_LIMIT_WINDOW=300
RENYYT_RATE_LIMIT_BLOCK=600
RENYYT_RATE_LIMIT_CLEANUP_INTERVAL=300
RENYYT_RATE_LIMIT_WHITELIST=
```

Käänteisen välityspalvelimen takana asiakas-IP päätellään `X-Forwarded-For`-ketjusta vain luotetulta välityspalvelinlta ja ketjua käydään oikealta vasemmalle, jotta asiakkaan itse syöttämä vasemman reunan arvo ei kierrä rajoitusta.

## HTTP-kovennukset

`POST /api/v1/renyyt` hyväksyy vain `application/json`- tai `application/*+json`-sisällön. `Content-Length` vaaditaan, runko on oletuksena enintään 16 KiB ja liian suuri pyyntö palauttaa HTTP 413:n. Hidas asiakasyhteys aikakatkaistaan oletuksena 30 sekunnissa. Tunnetut mutta tukemattomat HTTP-metodit palauttavat HTTP 405:n ja `Allow: GET, HEAD, POST, OPTIONS` -otsakkeen.

```text
RENYYT_MAX_REQUEST_BODY=16384
RENYYT_CLIENT_SOCKET_TIMEOUT=30
```

## Hallittu sammutus

Palvelin käsittelee sekä Ctrl-C:n että `SIGTERM`:in siististi. Tämä sopii systemd- ja Docker-käyttöön: prosessi lopettaa uusien pyyntöjen vastaanoton, sulkee kuuntelusoketin ja `ThreadingHTTPServer` odottaa oletusarvoisesti käynnissä olevien ei-daemonisten pyyntösäikeiden päättymistä ennen prosessin poistumista. `deploy/systemd/renyyt.service.example` käyttää `SIGTERM`:iä ja `TimeoutStopSec`-rajaa, ja Dockerfile määrittelee `STOPSIGNAL SIGTERM`.

## Käyttöliittymän apufunktioiden testit

Aikaan ja tyhjennysväleihin liittyvät puhtaat käyttöliittymäfunktiot ovat `web/helpers.js`-tiedostossa, joka toimii sekä selaimessa että Node.js:n CommonJS-testissä. Testit ajetaan:

```bash
node tests/test_frontend.js
```

Ne kattavat mm. peruspolun päättelyn, ISO-viikon, vuodenvaihteen ylittävät viikkovälit, kausittaisen tyhjennysvälin, päivälaskennan ja kimppaosuuden pyöristyksen.

Koontiputki testataan erikseen:

```bash
PYTHONPATH=src python3 -m unittest -v tests.test_build
```

Koko palvelintestistö:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_frontend.js
```

## systemd-esimerkki

Paketissa on `deploy/systemd/renyyt.service.example`. Tyypillisessä asennuksessa sovellus kopioidaan esimerkiksi `/opt/renyyt`-hakemistoon, juuren `.env.example` kopioidaan ja muokataan tarvittaessa `/etc/renyyt/renyyt.env`:ksi ja palveluyksikkötiedosto `/etc/systemd/system/renyyt.service`:ksi. Esimerkkipalvelun `EnvironmentFile=-/etc/renyyt/renyyt.env` lukee tämän tiedoston systemd:n kautta; vaihtoehtoisesti Renyyt voi lukea oman `.env`-tiedostonsa suoraan. Esimerkkipalvelu ajaa `scripts/build.py`:n ennen käynnistystä, käynnistää palvelimen automaattisesti uudelleen virheessä ja käyttää systemd/journald-lokitusta.

Tarkista aina käyttäjä, ryhmä, hakemistot ja käänteisen välityspalvelimen osoitteet oman järjestelmän mukaan ennen käyttöönottoa.

## Docker-esimerkki

Mukana oleva `Dockerfile` käyttää `python:3.13-slim`-peruskuvaa eikä asenna sovellukselle lisäpaketteja. Konttikuvan koonti ajaa sisältötunnisteisiin perustuvan tuotantokoosteen automaattisesti:

```bash
docker build -t renyyt .
docker run --rm --read-only -p 127.0.0.1:8787:8787 renyyt
```

Kontti ajaa sovelluksen erillisellä ei-root `renyyt`-käyttäjällä, estää Pythonin `.pyc`-kirjoitukset ajon aikana ja tarvitsee normaalikäytössä vain lukuoikeuden tiedostojärjestelmään. OCI-metatiedot voi antaa koonnissa `RENYYT_VERSION`, `VCS_REF` ja `BUILD_DATE` koontiargumentteina.

Käänteisen välityspalvelimen ja kontin ollessa eri verkoissa `RENYYT_TRUSTED_PROXIES` pitää asettaa välityspalvelinn todelliseen container-/verkko-osoitteeseen tai CIDR-verkkoon.

## GitHub ja julkaisupaketti

`.github/workflows/ci.yml` ajaa Python-testit Python 3.8/3.13 -versioilla, käyttöliittymätestit, tuotantokoosteen, syntaksitarkistukset ja Docker-koosteen sekä kontin käynnistys- ja sammutustarkistukset. Jos muutos koskee vain `Dockerfile`- ja/tai `.dockerignore`-tiedostoja, selainten asennus, toiminnalliset E2E-testit ja kuvavertailut ohitetaan. Muut muutokset ja käsin käynnistetty CI ajavat myös selaintestit. `release.yml` ajaa perusvarmistuksen `v*`-tageille ja julkaisee `scripts/package.py`:n tekemän `.tar.gz`-julkaisupaketin GitHub-julkaisuun.

Paikallinen julkaisupaketti tehdään:

```bash
python3 scripts/build.py
python3 scripts/package.py
```

Paketointiskripti jättää pois kaikki generoidut `.gz`-representaatiot, `__pyvälimuisti__`-hakemistot, `.pyc`-tiedostot ja aiemmat `.tar.gz`-paketit. `CONTRIBUTING.md` ja `SECURITY.md` sisältävät kehitys- ja turvallisuusohjeet.

Projekti käyttää MIT-lisenssiä; `LICENSE` sisältyy sekä repoon että julkaisupakettiin.

### Tekoälyavusteinen kehitys

Repojuuren englanninkielinen `AGENTS.md` on yhteinen tekninen ohjeistus tekoälyavustajille ja ihmiskehittäjille. GitHub Copilotia varten `.github/copilot-instructions.md` tiivistää samat keskeiset säännöt. Ohjeet kattavat muun muassa Python 3.8+ -yhteensopivuuden, riippuvuuksien minimoinnin, tietosuojan, käyttöliittymä- ja CSP-säännöt, testauksen, koosteen ja julkaisukäytännöt.

## GitHub-julkaisu

Ennen ensimmäistä julkista julkaisua kannattaa asettaa repositorion lyhyt kuvaus ja aihetunnisteet. Sopivia esimerkkejä ovat `finland`, `waste-management`, `self-hosted`, `python`, `prometheus` ja `openmetrics`. Julkaisutyönkulku muodostaa versioidun `.tar.gz`-julkaisupaketin tageille, joiden versio vastaa `VERSION`-tiedostoa. Käytännön julkaisutarkistuslista on tiedostossa `.github/release-checklist.md`.


### Brändiresurssit

Master-logo sekä selain- ja mobiilikuvakkeet sijaitsevat hakemistossa `web/assets/brand/`. `logo.svg` on käyttöliittymässä käytettävä mukautuva master-logo. Samasta merkistä tuotetaan SVG/ICO-favicon, Apple touch -kuvake, tavalliset 192/512 PNG-kuvakkeet sekä `site.webmanifest`-tiedostossa viitatut maskable-192/512-kuvakkeet. Julkaisupaketit sisältävät nämä resurssit, mutta eivät valmiiksi pakattuja `.gz`-tiedostoja.
## Käyttöönottoesimerkit

Valmiit esimerkit löytyvät `deploy/`-hakemistosta:

- `deploy/nginx/renyyt.conf.example` — nginx + TLS + peruspolku
- `deploy/caddy/Caddyfile.example` — Caddy, joka riisuu `/renyyt`-etuliitteen taustapalvelulta
- `deploy/systemd/` — systemd sekä nginx-yhteiskäytön huomioita
- `deploy/cloud-run/README.md` — Cloud Run / palvelimeton kontti

Tuotannossa käänteisen välityspalvelimen kannattaa yleensä hoitaa TLS sekä gzip/Brotli. Python-palvelin voidaan pitää localhostissa pakkaamattomana.

## API:n versiointi

Käyttöliittymä käyttää rajapintapolkua `POST /api/v1/renyyt`. Uusi major-API-versio voidaan myöhemmin lisätä erikseen, jos rajapintaan tarvitaan rikkovia muutoksia.

## Taustapalvelun rakenteen diagnostiikka

`RENYYT_LOG_LEVEL=DEBUG` kirjaa Oma jätehuolto -upstream-pyyntöjen vaiheet, endpointin loogisen nimen, HTTP-statuksen, sisältötyypin, vastekoon ja keston sekä Renyyn vastauksesta havaitut aiemmin tuntemattomat pää-, `tariff`- ja `kimppa`-kentät rakennetyyppeineen. DEBUG ei kirjaa käyttäjätunnusta, salasanaa, asiakasnumeroita, pyyntö-URLien arkaluonteisia query-arvoja eikä vastausten sisältöä. `RENYYT_LOG_LEVEL=TRACE` lisää tarkoituksella arkaluonteisen **JSON-diagnostiikan**: selaimelta Renyyt-API:lle vastaanotettu JSON-pyyntö (myös tunnukset) sekä Oma jätehuolto -palvelusta ja Renyyt-API:sta palautuva JSON voidaan kirjoittaa lokiin. Kirjautumissivun HTML:ää, JavaScriptiä tai muuta ei-JSON-upstream-sisältöä ei TRACEssa kirjata. SMTP:n TRACE on erillinen ja voi edelleen sisältää SMTP-tunnuksia, viestin sisällön ja protokollavastauksia. Havaintojen määrä näkyy myös metriikassa `renyyt_upstream_unknown_fields_total`.


### Playwright, linttaus ja coverage

Kehitystyökalut asennetaan Pythonille komennolla `python3 -m pip install -e '.[dev]'` ja JavaScriptille komennolla `npm install`. Python-linttaus ajetaan komennolla `ruff check src tests scripts run.py`, coverage komennolla `PYTHONPATH=src coverage run --branch -m unittest discover -s tests -p 'test_*.py' && coverage report` ja JavaScript-linttaus komennolla `npm run lint:js`. Coverage-raja on 78 %, joka vastaa tämän version nykyistä regressiotestien baselinea; CI estää kattavuuden putoamisen sen alle.

Playwright-testit ajetaan komennolla `npx playwright install chromium` ja sen jälkeen `npm run test:e2e`. E2E-sarja kattaa kirjautumisen ja tallennetut tunnukset, kielenvaihdon, embed-näkymän, automaattisen ja oman järjestyksen drag & drop -toiminnon, tänään/huomenna/tällä viikolla -merkinnät, README/API/TECHNICAL-dokumenttidialogit, PWA-asennuspainikkeen, responsiivisen headerin sekä service workerin offline-app-shellin. CI asentaa Chromiumin automaattisesti.

## Toistettavat buildit

`SOURCE_DATE_EPOCH` vakioi tuotantobuildin ja release-arkiston aikaleimat. Komento `python scripts/check_reproducible.py` rakentaa projektin kahdesti erillisissä hakemistoissa samalla epoch-arvolla ja varmistaa byte-for-byte-identtisyyden sekä release-arkistolle että wheelille. Sama tarkistus ajetaan CI:ssä Python 3.11:llä.

## Web Push -tyhjennysmuistutukset

Muistutukset ovat erillinen, oletuksena pois käytöstä oleva ominaisuus. Renyytin perusasennus säilyy ilman Web Push -runtime-riippuvuuksia. Ominaisuus asennetaan:

```bash
pip install 'renyyt[push]'
```

Python 3.8/3.9 käyttää yhteensopivaa `pywebpush 1.14.1` -versiota; Python 3.10+ käyttää `pywebpush 2.x` -sarjaa. Tuore pywebpush 2.x vaatii Python 3.10+:n, minkä vuoksi extra on version ehdollinen.

### Tietomalli

Muistutukset käyttävät `sqlite3`-standardikirjastoa. Palvelimelle tallennetaan:

- selaimen Web Push -subscription (`endpoint`, `p256dh`, `auth`)
- UI-kieli
- tyhjennyspäivä
- käyttäjälle näytettävä jätelajin/palvelun nimi
- laskettu UTC-muistutushetki
- tieto onnistuneesta lähetyksestä.

Renyy-asiakasnumeroa, salasanaa tai upstream-cookieita **ei tallenneta**. Push-endpoint on itsessään salainen capability-URL ja tietokanta pitää suojata kuten muu palvelimen yksityinen runtime-data. Selain korvaa vielä lähettämättömän muistutuslistan uudella snapshotilla jokaisen onnistuneen tyhjennyshaun jälkeen. Jo lähetettyä täysin identtistä muistutusta ei luoda uudelleen pelkän uuden synkronoinnin vuoksi.

### Konfiguraatio

```dotenv
RENYYT_REMINDERS_ENABLED=true
RENYYT_REMINDERS_DB=/var/lib/renyyt/reminders.sqlite3
RENYYT_VAPID_PRIVATE_KEY=...
RENYYT_VAPID_PUBLIC_KEY=...
RENYYT_VAPID_SUBJECT=mailto:admin@example.com
RENYYT_PUSH_TTL=86400
```

VAPID-arvot voi generoida push-extran asentamisen jälkeen:

```bash
renyyt reminders generate-vapid
```

Komento tulostaa `.env`-muotoiset private/public-arvot. `RENYYT_VAPID_SUBJECT` asetetaan erikseen `mailto:`- tai `https://`-URI:ksi.

### Sisäinen scheduler

Yksinkertaiseen jatkuvasti käynnissä olevaan palvelimeen voi käyttää serveriprosessin omaa scheduleriä:

```dotenv
RENYYT_REMINDERS_INTERNAL_SCHEDULER=true
RENYYT_REMINDERS_RUN_TIMES=07:00,18:00
RENYYT_REMINDERS_TIMEZONE=Europe/Helsinki
```

Scheduler nukkuu seuraavaan määritettyyn kellonaikaan eikä pollaa tietokantaa muutaman minuutin välein. `local` käyttää palvelimen omaa aikavyöhykettä ja `UTC` toimii kaikilla tuetuilla Python-versioilla. Muut IANA-aikavyöhykkeet käyttävät Pythonin `zoneinfo`-moduulia ja edellyttävät Python 3.9+:aa.

### Ulkoinen scheduler / serverless

Kun HTTP-prosessi ei ole jatkuvasti elossa, sisäinen scheduler jätetään pois ja erääntyneet muistutukset käsitellään kertaluontoisella komennolla:

```bash
renyyt reminders run-due
```

Komento avaa saman SQLite-storen, lähettää sillä hetkellä erääntyneet pushit ja poistuu. Sen voi käynnistää esimerkiksi systemd timerilla, cronilla tai pilvipalvelun scheduled job/function -mekanismilla. Sovelluslogiikka on myös `renyyt.reminders.run_due()`-funktiona, joten provider-kohtainen scheduled function voi kutsua samaa ydintoimintoa ilman julkista HTTP-admin-endpointia.

SQLite sopii yhden pysyvän palvelimen asennukseen. Serverless-ympäristössä, jossa paikallinen levy ei ole pysyvä tai instansseja on useita, tarvitaan myöhemmin erillinen pysyvä `ReminderStore`-adapteri (esim. PostgreSQL/pilven tietokanta). Nykyinen ensimmäinen toteutus ei yritä teeskennellä paikallista SQLitea jaetuksi serverless-storeksi.

### Selain ja PWA

Muistutukset edellyttävät PWA/service worker -toimintoa (`RENYYT_PWA_ENABLED=true`), HTTPS-yhteyttä tuotannossa ja selaimen myöntämää notification-lupaa. Käyttöliittymä pyytää lupaa vain käyttäjän painaessa muistutusten käyttöönottopainiketta. Service worker vastaanottaa `push`-eventin, näyttää pysyvän käyttöjärjestelmäilmoituksen ja avaa Renyytin ilmoitusta klikattaessa.

Android/Chromiumissa Web Push toimii tavallisena web-standardina. iOS/iPadOS:ssa Web Push edellyttää Home Screenille lisättyä web-appia (iOS/iPadOS 16.4+). Selain/push-palvelu voi toimittaa viestin vaikka Renyyt-sivu ei olisi sillä hetkellä auki.

### Muistutusten päivittyminen

Koska palvelin ei tallenna upstream-tunnuksia, se ei voi oma-aloitteisesti hakea muuttuneita tyhjennyspäiviä Renyystä. Muistutukset ovat viimeksi onnistuneen selainhaun snapshot. Kun käyttäjä avaa Renyytin ja data päivittyy, selain synkronoi myös muistutuslistan. Tämä on tietoinen yksityisyysraja: upstream-tunnuksia ei tallenneta vain taustapäivitysten vuoksi.
