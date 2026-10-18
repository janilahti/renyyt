# Cloud Run

Peruskontti käyttää Python 3.13:a ja sopii HTTP-palveluksi Cloud Runiin.
Cloud Run antaa `PORT`-muuttujan, jota käytetään, ellei `RENYYT_PORT` ole asetettu.
Älä aseta ristiriitaista RENYYT_PORT-arvoa Cloud Runin portin rinnalle.

```bash
docker build -t renyyt:latest .
```

Sovita rekisteri, projekti, alue ja julkinen/yksityinen pääsy omaan käyttöönottoon.
Kontti ei asenna push-extraa. Kuva ei saa sisältää `.env`-salaisuuksia tai asiakasdataa;
anna tarvittavat salaisuudet palvelun asetuksilla/Secret Managerilla.

```dotenv
RENYYT_HOST=0.0.0.0
RENYYT_LOG_LEVEL=INFO
RENYYT_LOG_FORMAT=json
RENYYT_REMINDERS_ENABLED=false
RENYYT_REMINDERS_INTERNAL_SCHEDULER=false
```

Määritä ulkoiset Host-/Origin-arvot ja luotetut proxyt käyttöönoton topologian
mukaan. Älä luota kaikkiin lähdeosoitteisiin vain X-Forwarded-otsakkeiden vuoksi.
Palvelimen `/health` ja `/ready` eivät kirjaudu Renyyhyn tai tarkista upstreamin
saatavuutta. Rajaa metriikoiden ulkoinen käyttö tarvittaessa.

Rate limiter, muistivälimuisti ja metriikat ovat prosessi-/instanssikohtaisia;
ne eivät muodosta globaalia rajaa tai yhteistä cachea usealle instanssille.

Paikallinen SQLite ei ole pysyvä jaettu muistutusstore serverless-käytössä.
Nykyisen toteutuksen muistutuksia ei tule ottaa käyttöön oletusarvoisella
Cloud Runin katoavalla levyllä. Tarvitaan erikseen suunniteltu pysyvä store-adapteri
ja ulkoinen scheduler; sisäinen scheduler ei ole luotettava nukutettavalla
instanssilla. Tavallinen tyhjennysten haku toimii ilman muistutuksia.

Yhteiset asetukset ja rajoitukset: [TECHNICAL.md](../../TECHNICAL.md).
