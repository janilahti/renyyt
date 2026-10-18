# Renyyt HTTP API

Tämä dokumentti kuvaa sovelluksen oman HTTP-rajapinnan. Rajapinta ei ole Renyyn virallinen API.

## `POST /api/v1/renyyt`

Hakee tyhjennyspalvelut käyttäjän Renyy-tunnuksilla.

Pyyntö:

```json
{
  "username": "01-0000000-00",
  "password": "salasana",
  "suffixes": []
}
```

Onnistunut vastaus sisältää `services`-listan, mahdollisen `warnings`-listan sekä datan tuoreutta kuvaavat kentät:

```json
{
  "services": [],
  "customerNumbers": [],
  "warnings": [],
  "upstreamFetchedAt": "2026-10-04T18:42:31Z",
  "upstreamAgeSeconds": 37,
  "dataSource": "upstream"
}
```

`upstreamFetchedAt` on hetki, jolloin data todella saatiin Oma jätehuolto -upstreamista. `upstreamAgeSeconds` lasketaan uudelleen juuri ennen jokaista vastausta, joten cache-hitillä se kertoo cached datan todellisen iän. `dataSource` on normaalisti `upstream`, muistivälimuistista palvellessa `memory-cache` ja fixture-tilassa `fixture`. Fixture-datalla upstream-aikaleima ja ikä ovat `null`, koska oikeaa upstream-hakua ei tapahdu. Palvelin ei tallenna tunnuksia.

Tunnettuja virhekoodeja ovat `AUTH_FAILED`, `MISSING_CREDENTIALS`, `UPSTREAM_TIMEOUT`, `UPSTREAM_CONNECTION_ERROR`, `UPSTREAM_INVALID_JSON`, `UPSTREAM_SCHEMA_ERROR` ja `RATE_LIMITED`.

### Palvelinmuistivälimuisti

Jos `RENYYT_CACHE_MAX_ENTRIES` ja `RENYYT_CACHE_TTL_SECONDS` on aktivoitu, onnistunut vastaus voidaan palvella prosessin muistista ilman uutta Oma jätehuolto -kutsua. Cache-avain muodostetaan HMAC-tiivisteenä koko autentikoidusta pyynnöstä, joten eri tunnukset tai suffix-listat eivät jaa vastausta. `X-Renyyt-Cache` on `HIT`, `MISS` tai `DISABLED`. Cache-hit säilyttää alkuperäisen `upstreamFetchedAt`-arvon, päivittää `upstreamAgeSeconds`-arvon vastaushetkelle ja asettaa `dataSource`-arvoksi `memory-cache`.

## `GET /api/v1/features`

Palauttaa käyttöliittymälle vain palvelimen julkiset ominaisuusliput. Vastaus sisältää `feedback`- ja `pwa`-liput sekä `reminders`-objektin. `pwa` kertoo, ovatko manifesti, install-UI ja service worker käytössä. `reminders.enabled` kertoo, onko Web Push -muistutusominaisuus käytössä, ja tällöin `reminders.vapidPublicKey` sisältää selaimelle tarkoitetun julkisen VAPID-avaimen. SMTP- tai VAPID-private-asetuksia ei koskaan palauteta selaimelle.

## `POST /api/v1/feedback`

Käytettävissä vain, jos SMTP-palaute on konfiguroitu. JSON-runko sisältää `message`-kentän, valinnaisen `email`-kentän ja tarvittaessa käyttäjän nimenomaisesti valitseman `collectionData`-JSON-kentän. `email` lisätään viestin `Reply-To`-otsakkeeseen vain, jos se on turvallisesti yksittäisen sähköpostiosoitteen muotoinen; muussa tapauksessa se jää vain viestin tekstiosan Reply address -riville. Viestin enimmäispituus on 4000 merkkiä. Palvelin lisää sähköpostiin sovellusversion, pyyntötunnisteen ja rajatun User-Agent-tiedon. Jos `collectionData` on mukana, se liitetään sähköpostiin `renyyt-collection-data.json`-tiedostona; oletusraja on 262144 tavua ja sitä voi säätää `RENYYT_FEEDBACK_MAX_DATA_BYTES`-asetuksella. Kirjautumistunnuksia tai salasanaa ei pidä sisällyttää `collectionData`-kenttään. Lähetyksellä on erillinen IP-kohtainen pyyntöraja.

## Muut endpointit

- `GET /api/v1/features` – käyttöliittymän julkiset ominaisuusliput.
- `GET /health` – prosessin elossaolotarkistus.
- `GET /ready` – runtime-resurssien ja buildin readiness.
- `GET /version` – versio, build ja API-versiot.
- `GET /metrics` – Prometheus text exposition 0.0.4.
- `GET /metrics/openmetrics` – OpenMetrics 1.0.
- `GET /README.md` ja `GET /CHANGELOG.md` – dokumentit.
- `GET /service-worker.js` – PWA:n app-shell service worker.

`HEAD` toimii myös GET-reiteillä, mukaan lukien `/api/v1/features`.

Kaikissa deploy-malleissa base path voi olla käytössä. Selainfrontti muodostaa endpointit automaattisesti nykyisen base pathin alle.

## Web Push -muistutukset

Kun muistutukset on otettu palvelimella käyttöön, `GET /api/v1/features` sisältää lisäksi julkisen VAPID-avaimen:

```json
{
  "reminders": {
    "enabled": true,
    "vapidPublicKey": "..."
  }
}
```

Private VAPID -avainta ei palauteta selaimelle.

### `POST /api/v1/reminders/sync`

Synkronoi selaimen push-subscriptionin ja vielä lähettämättömät muistutukset. Pyyntö sisältää selaimen `PushSubscription.toJSON()`-rakenteen, UI-kielen ja listan muistutuksista (`collectionDate`, `label`, `triggerAt`). Endpoint ei ota vastaan eikä tarvitse Renyy-kirjautumistunnuksia.

### `POST /api/v1/reminders/unsubscribe`

Poistaa kyseisen push-subscriptionin ja siihen liittyvät muistutukset palvelimelta. Selain poistaa lisäksi oman push-subscriptioninsa Push API:n kautta.

## Yhteiset pyyntö- ja virhesäännöt

Kaikki POST-reitit käyttävät Host-/Origin-tarkistusta. `Origin`-otsakkeen mukana
ollessa sen on vastattava sallittua ulkoista originia; curl ilman Originia toimii.
Proxy-otsakkeisiin luotetaan vain määritetyiltä proxy-IP:iltä. `RENYYT_BASE_PATH`
lisätään kaikkien reittien eteen, esimerkiksi `/renyyt/api/v1/renyyt`.

Runko on JSON-objekti, Content-Type `application/json` tai `application/*+json` ja
Content-Length vaaditaan. Tavallinen enimmäiskoko on 16384 tavua; palautereitti
sallii suuremman rungon liitteen kokorajan mukaisesti. Vastaukset käyttävät
`Cache-Control: no-store`, ja `X-Request-ID` auttaa lokien jäljityksessä.

Virheen rakenne:

```json
{"error": "Asiakasnumero ja salasana ovat pakollisia.", "code": "MISSING_CREDENTIALS"}
```

HTTP-tiloja ovat mm. 400 (puuttuva tunnus tai virheellinen JSON/rakenne),
401 (`AUTH_FAILED`), 403 (Host/Origin), 404 (pois käytöstä
oleva ominaisuus), 411 (puuttuva pituus), 413 (liian suuri runko),
415 (sisältötyyppi), 429 (rajoitus), 502 (upstream, myös `AUTH_SESSION_FAILED`, tai SMTP) ja 504 (aikakatkaisu).
429 voi sisältää `Retry-After`-otsakkeen. `error` on ihmiselle tarkoitettu teksti;
asiakasohjelman kannattaa tulkita `code`-arvoa. Tuntematon upstream-rakenne voi
tuottaa varoituksia onnistuneeseen vastaukseen ilman kaikkien palveluiden hylkäämistä.

Muistutusten sync-pyynnön kentät ovat `subscription`, `locale` (oletus `fi`) ja
`reminders`. Subscription on selaimen `PushSubscription.toJSON()`-objekti, jossa
on HTTPS-`endpoint` ja `keys.p256dh`/`keys.auth`. Muistutus sisältää `collectionDate`,
`label` ja aikavyöhykkeen sisältävän ISO-8601-`triggerAt`-ajan. Lista on enintään
128 alkiota; yli tunnin vanhat lähetyshetket ohitetaan ja yli 370 päivää tulevaisuuteen
osuvat hylätään. Sync korvaa vielä lähettämättömän snapshotin, ei hae Renyystä.

Syncin onnistunut vastaus on `{"ok":true,"subscribed":true,"reminders":2,"subscriptionId":"..."}`.
Unsubscribe ottaa saman `subscription`-objektin ja palauttaa
`{"ok":true,"subscribed":false}`. Virheellinen pyyntö tuottaa
`INVALID_REMINDER_REQUEST`-virheen (400); pois käytöstä oleva ominaisuus
`REMINDERS_DISABLED`-virheen (404). Subscription-avaimet ja endpointit ovat salaisia,
eikä subscriptionId:n lyhennettä pidä käyttää kirjautumistunnisteena.

Palaute palauttaa onnistuessaan `{"ok":true}`. Pois käytöstä oleva palaute tuottaa
`FEEDBACK_DISABLED`-virheen (404), SMTP-timeout `FEEDBACK_SMTP_TIMEOUT`-virheen (504).

Palvelin tarjoaa myös dokumentit `/API.md` ja `/TECHNICAL.md`,
brändiresurssit `/brand/...` ja PWA:n ollessa käytössä manifestin
`/brand/site.webmanifest`. Service worker ja manifesti palauttavat 404:n, kun PWA on pois
käytöstä. `/health` ja `/ready` eivät testaa käyttäjän tunnuksia tai Renyyn saatavuutta;
readiness-virheen HTTP-status on 503. HEAD ja OPTIONS eivät tarvitse tunnuksia.
