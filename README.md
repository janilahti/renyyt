# Renyyt – seuraavat tyhjennykset

Kevyt web-käyttöliittymä ja pieni välityspalvelin Pirkanmaan Jätehuollon Renyyn Oma jätehuolto -palvelun jäteastioiden seuraavien tyhjennyspäivien näyttämiseen.

- [Projektin julkinen repository](https://github.com/janilahti/renyyt)
- [Renyyn (Pirkanmaan Jätehuolto) virallinen sivusto](https://renyy.fi/)
- [Oma jätehuolto -palvelu](https://renyy.fi/palvelut/oma-jatehuolto/)
- [Tekninen dokumentaatio](TECHNICAL.md)

## Pikakäynnistys

Tarvitset Python 3:n:

```bash
git clone https://github.com/janilahti/renyyt.git renyyt
cd renyyt
python3 run.py
```

Avaa selaimessa [http://127.0.0.1:8787](http://127.0.0.1:8787).

Tiedostossa [TECHNICAL.md](TECHNICAL.md) on yksityiskohtaiset ohjeet mm. asennusta, kehitystä, käänteisen välityspalvelimen käyttöä, metriikoiden seurantaa ja Docker-kontin rakentamista varten.

Mukana oleva Dockerfile käyttää Python 3.13:a. Suoraan Pythonilla ajettuna
sovellus tukee edelleen Python 3.8:aa ja uudempia versioita.

Kehitys- ja E2E-testauksessa upstream voidaan korvata paikallisella JSON-fixturella `RENYYT_FIXTURE_FILE`-asetuksella; tarkemmat ohjeet ovat TECHNICAL.md:ssä.

## Käyttöliittymän kielet

Käyttöliittymän oletuskieli on suomi. Mukana ovat lisäksi englanti, ruotsi ja ukraina. Kielivalinta tallennetaan selaimeen ja upotus-URL voi välittää valinnan `lang=fi`, `lang=en`, `lang=sv` tai `lang=uk` -parametrilla. Uusia kieliä voi lisätä ilman ulkoisia kirjastoja täydentämällä `web/i18n.js`-sanakirjaa ja kielimetatietoja. README-tiedostoa ei lokalisoida käyttöliittymän mukana.

Arabiaa ja persiaa/farsia ei ole vielä otettu mukaan, koska ne kirjoitetaan oikealta vasemmalle (RTL) ja niiden lisääminen edellyttää erillisen RTL-asettelun testaamista.

## Lisääminen aloitusnäyttöön

Sovelluksessa on vapaaehtoinen **Asenna**-painike. Chromium-pohjaisissa selaimissa painike tulee näkyviin vain, kun selain ilmoittaa sovelluksen olevan asennettavissa; selainpromptia ei avata automaattisesti. iOS/Safarissa painike näyttää ohjeen selaimen **Jaa → Lisää Koti-valikkoon** -toiminnon käyttämiseen.

Kun `RENYYT_PWA_ENABLED=true` (oletus), Web App Manifest käynnistää asennetun sovelluksen suoraan `/embed`-näkymään. Jos URL ei sisällä tunnuksia, upotusnäkymä käyttää saman originin `localStorage`en aiemmin tallennettuja tunnuksia. Asennettavuus edellyttää tuotannossa HTTPS:ää (localhost/127.0.0.1 kelpaa kehityksessä). PWA-tilassa sovelluksessa on service worker, joka säilyttää viimeksi käytetyn sovelluskuoren selaimen välimuistissa. Asetuksella `RENYYT_PWA_ENABLED=false` asennus-UI, manifesti ja service worker poistuvat kokonaan käytöstä. Jos palvelimeen tai Renyyhin ei saada yhteyttä, käyttöliittymä voi näyttää viimeksi onnistuneesta hausta tallennetun supistetun tyhjennysdatan selvästi vanhentuneeksi merkittynä.


## Tyhjennysnäkymän työkalut

Tyhjennyskortit voi näyttää automaattisesti seuraavan tyhjennyspäivän mukaisessa aikajärjestyksessä tai käyttäjän omassa järjestyksessä. Oma järjestys tallennetaan selaimeen ja sitä voi muuttaa vetämällä kortteja tai nuolipainikkeilla. Lisäksi käyttöliittymässä on kompakti korttinäkymä ja `.ics`-kalenterivienti seuraavista tyhjennyksistä.

**Astiat**-asetuksista voi lisäksi valita jäteastiakohtaisesti, näkyykö astia normaalissa näkymässä, upotusnäkymässä ja muistutuksissa. Upotusnäkymä ja muistutukset perivät oletuksena normaalin näkymän valinnan, mutta niille voi määrittää oman poikkeuksen. Valinnat tallennetaan selaimeen. Upotus-URL kuljettaa erillisessä sumennetussa `view`-blobissa tehokkaan astiarajauksen, järjestystilan, manuaalisen järjestyksen ja kompaktin näkymän myös silloin, kun URL:ssa ei ole kirjautumistietoja. Näin sama upotusnäkymä voidaan siirtää toiseen selaimeen tai laitteeseen.

Jokaisen kortin **Olennaiset lisätiedot** kokoaa API:n keskeisiä arvoja helpommin luettavaan muotoon. Alkuperäinen raakadata säilyy erikseen avattavana.

### Viimeksi tallennettu data

Onnistuneesta hausta tallennetaan selaimeen supistettu kopio korttien keskeisistä tiedoista. Koko raakaa API-vastausta tai kimppaosakkaiden henkilötietorakenteita ei tallenneta tähän välimuistiin. Jos uusi haku epäonnistuu yhteys- tai taustapalveluvirheeseen, viimeksi tallennettu tieto voidaan näyttää aikaleiman kanssa vanhentuneena.

## Miksi välityspalvelin tarvitaan?

Renyyn/Pirkanmaan Jätehuollon Oma jätehuolto sijaitsee eri alkuperässä (`extranet.pjhoy.fi`) ja käyttää palvelinsessiota. Tavallinen staattinen selain-JavaScript ei voi luotettavasti tehdä kirjautumista ja lukea rajapinnan vastausta CORS- ja evästerajoitusten vuoksi. `src/renyyt/server.py` tekee vain tämän välityksen ja tarjoilee saman `index.html`-sivun.

## Tunnusten tallennus

- Oletus: tunnuksia ei tallenneta selaimeen.
- Jos rastitat **Tallenna**, asiakasnumero, salasana ja mahdolliset asiakasnumeron loppuosat tallennetaan selaimen `localStorage`en AES-GCM-pohjaisena sumennettuna blobina. Avaimen tallentaminen saman datan yhteyteen tarkoittaa, ettei kyse ole turvallisesta salauksesta.
- Älä käytä tallennusta jaetulla tai muuten epäluotetulla laitteella.
- Python-palvelin ei tallenna tunnuksia levylle.
- Salasanakentän **Näytä**-painike aktivoituu vain, kun kentän koko nykyinen sisältö on käyttäjän itse syöttämää: joko kirjoittaminen aloitetaan tyhjästä kentästä tai koko aiempi sisältö korvataan kerralla. Pelkkä merkin lisääminen localStoragesta palautetun salasanan perään ei aktivoi näyttötoimintoa.

## Käytetyt rajapintapolut

- `https://extranet.pjhoy.fi/pirkka/j_acegi_security_check?target=2`
- `https://extranet.pjhoy.fi/pirkka/secure/get_services_by_customer_numbers.do`

Toteutus näyttää ainakin API-kentät:

- `ASTNextDate` – seuraava tyhjennyspäivä
- `ASTVali` – tyhjennysväli viikkoina
- `ASTNimi` – palvelun nimi
- `tariff.productgroup` – jätelajin tuoteryhmä

Jokaisessa kortissa on lisäksi avattava raakadata, jotta muut rajapinnan tarjoamat kentät ovat nähtävissä ilman että käyttöliittymä arvaa niiden merkitystä.

## Huomio

Rajapinta ei ole tässä muodossa dokumentoitu julkiseksi API:ksi, joten Renyy/Pirkanmaan Jätehuolto voi muuttaa sitä milloin tahansa.

## Raakadatan haku komentoriviltä

Paikallinen palvelin tarjoaa saman datan JSON-muodossa endpointista `POST /api/v1/renyyt`. Käyttöliittymän **Näytä HTTP-kutsu** -painike muodostaa sekä raakamuotoisen HTTP-esimerkin että valmiin `curl`-komennon lomakkeelle syötetyillä tunnuksilla (tai placeholdereilla, jos kentät ovat tyhjiä). Samassa dialogissa voi ladata testattavaksi tallennetun Oma jätehuolto -JSON-vastauksen tai Renyyt-API:n JSON-vastauksen. Tiedosto käsitellään vain selaimessa.

Esimerkiksi:

```bash
curl --request POST 'http://127.0.0.1:8787/api/v1/renyyt' \
  --header 'Content-Type: application/json' \
  --data-binary @- <<'JSON'
{
  "username": "<ASIAKASNUMERO>",
  "password": "<SALASANA>",
  "suffixes": []
}
JSON
```

## Upotusnäkymä

Sivulla on **Upotusnäkymä**-painike, joka piilottaa kirjautumisen, teemanvalinnan, tietoturvatekstit ja muut hallintaelementit. Upotustilassa näkyvät vain tyhjennystiedot.

Itsekseen tiedot hakevan URL:n voi kopioida **Näytä HTTP-kutsu** -ikkunan **Upotus-URL**-kohdasta. Esimerkiksi:

```text
http://127.0.0.1:8787/embed#theme=system&lang=fi&credentials=v1....
```

Kirjautumistiedot ovat URL:n fragmentissa (`#...`), joten selain ei lähetä niitä GET-pyynnön mukana palvelimelle eikä palvelimen access-lokiin. URL itsessään sisältää silti salasanan, joten sitä pitää käsitellä salaisuutena.



## Upotustila

Upotusnäkymä avataan `/embed`-polulla; esimerkiksi `/embed#theme=dark`. Tuetut teemat ovat `system`, `light` ja `dark`. Jos fragmentissa ei ole `credentials`-blobia, sivu yrittää käyttää samalla originilla selaimen `localStorage`en tallennettuja tunnuksia. Tunnukset sumennetaan AES-GCM-pohjaiseen versionoituun blobiin, mutta avain kulkee saman blobin mukana, joten tätä ei pidä pitää turvallisena salauksena.

Tyhjennysnäkymä päivittää päivälaskurit vuorokauden vaihtuessa ja hakee automaattisesti uudet tiedot seuraavan tyhjennyspäivän jälkeen. Jos selain on ollut taustalla tai laite nukkumassa, päivitys tehdään näkyviin palatessa, jos ajastettu päivityshetki on jo ohitettu.

## Palaute

Palvelimen ylläpitäjä voi ottaa käyttöön käyttöliittymän **Palaute**-toiminnon SMTP-asetuksilla. Painike näkyy vain, kun palvelimelle on määritetty palautteen lähettämiseen tarvittavat asetukset. Selain lähettää normaalisti vain käyttäjän kirjoittaman viestin ja vapaaehtoisen vastausosoitteen; sähköpostiosoitteen muotoinen vastausosoite asetetaan myös viestin `Reply-To`-otsakkeeseen. Käyttäjä voi lisäksi nimenomaisesti valita selaimessa parhaillaan näkyvien tyhjennystietojen liittämisen JSON-tiedostona palautteeseen. Kirjautumistunnuksia tai salasanaa ei lisätä tähän liitteeseen. Tarkemmat SMTP-asetukset ovat [TECHNICAL.md](TECHNICAL.md)-tiedostossa.

## Lisenssi

Projekti on julkaistu [MIT-lisenssillä](https://opensource.org/license/mit).

## Saavutettavuus

Mobiilinäkymässä painikkeiden, valikoiden ja muiden lomakekontrollien kosketusalue
on vähintään 44 × 44 CSS-pikseliä; valintaruutujen kosketusalueeseen kuuluu niiden
teksti. Kapeissa näkymissä kortin päivämäärä sijoittuu jätelajin alapuolelle ja
dialogien sisältö rivittyy käytettävissä olevaan leveyteen. Astiat-dialogin valikot
asettuvat nimikkeidensä alle, jotta valitut arvot mahtuvat kokonaisina näkyviin.
Myös Järjestys-valikko saa oman rivinsä kapeimmissa näkymissä.

Käyttöliittymä tukee näppäimistöfokusta, natiivien dialogien fokuspalautusta, `prefers-reduced-motion`-asetusta sekä `forced-colors`/high-contrast-tilaa. Layout on tehty kestämään suurta selainzoomausta ilman, että tärkeät tekstit pakotetaan kiinteisiin leveyksiin.


## Rajapinta ja kehittäjät

Sovelluksen oman HTTP-rajapinnan kuvaus: [API.md](API.md). Testien ja CI-ajojen koontiohje on [TESTING.md](TESTING.md). Muut tekniset ajo-, proxy- ja build-ohjeet ovat [TECHNICAL.md](TECHNICAL.md)-tiedostossa.

## Epävirallisuus ja vastuu

Tämä on epävirallinen avoimen lähdekoodin asiakassovellus eikä Renyyn tai Pirkanmaan Jätehuollon virallinen tuote. Se käyttää asiakasportaalin rajapintaa, joka voi muuttua ilman ennakkovaroitusta. Käyttäjä vastaa omien tunnustensa turvallisesta käsittelystä ja siitä, että käyttö on palvelun ehtojen mukaista.


## Valinnainen palvelinmuistivälimuisti

Toistuvia identtisiä API-pyyntöjä voi nopeuttaa prosessin sisäisellä TTL/LRU-välimuistilla. Se on oletuksena pois käytöstä ja aktivoituu vasta, kun sekä `RENYYT_CACHE_MAX_ENTRIES` että `RENYYT_CACHE_TTL_SECONDS` ovat suurempia kuin nolla. Muistin kokonaismäärää rajaa lisäksi `RENYYT_CACHE_MAX_BYTES`. Tarkemmat asetukset ja tietoturvarajaukset ovat tiedostossa [TECHNICAL.md](TECHNICAL.md).

## Web Push -tyhjennysmuistutukset

Palvelin voi valinnaisesti tarjota PWA/Web Push -muistutuksia. Ominaisuus on oletuksena pois käytöstä eikä tavallinen Renyyt-asennus tarvitse sen Python-riippuvuuksia. Push-tuki asennetaan erikseen komennolla `pip install 'renyyt[push]'`.

Kun käyttäjä ottaa muistutukset käyttöön, selaimen push-subscription sekä seuraavien tyhjennysten päivät, nimet ja lasketut muistutushetket tallennetaan palvelimen SQLite-tietokantaan. Asiakasnumeroa, salasanaa tai upstream-session evästeitä ei tallenneta. Selain päivittää muistutuslistan aina onnistuneen tyhjennyshaun yhteydessä. Tarkemmat VAPID-, scheduler- ja serverless-ohjeet ovat [TECHNICAL.md](TECHNICAL.md)-tiedostossa.
