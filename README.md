# Renyyt – seuraavat tyhjennykset

[![Latest release](https://img.shields.io/github/v/release/janilahti/renyyt)](https://github.com/janilahti/renyyt/releases/latest)
[![License: MIT](https://img.shields.io/github/license/janilahti/renyyt)](https://github.com/janilahti/renyyt/blob/main/LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/janilahti/renyyt/ci.yml?branch=main&event=push&label=CI)](https://github.com/janilahti/renyyt/actions/workflows/ci.yml?query=branch%3Amain)
[![GHCR pulls/month](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjanilahti%2Frenyyt%2Fmain%2Fghcr-stats.json&query=%24.downloads_month_compact&label=ghcr%20pulls&suffix=%2Fmonth)](https://github.com/janilahti/renyyt/pkgs/container/renyyt)
[![GHCR pulls total](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjanilahti%2Frenyyt%2Fmain%2Fghcr-stats.json&query=%24.downloads_compact&label=ghcr%20pulls%20total)](https://github.com/janilahti/renyyt/pkgs/container/renyyt)
[![Release downloads/month](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjanilahti%2Frenyyt%2Fmain%2Frelease-stats.json&query=%24.downloads_month_compact&label=release%20downloads&suffix=%2Fmonth)](https://github.com/janilahti/renyyt/releases)
[![Release downloads total](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fjanilahti%2Frenyyt%2Fmain%2Frelease-stats.json&query=%24.downloads_compact&label=release%20downloads%20total)](https://github.com/janilahti/renyyt/releases)

Latausten kuukausiluvut tarkoittavat viimeisiä noin 30 päivää. Julkaisutiedostojen
kuukausikilpi näyttää aluksi `collecting`, kunnes seurantahistoriaa on kertynyt.

Kevyt web-käyttöliittymä ja välityspalvelin Renyyn (Pirkanmaan Jätehuolto) jäteastioiden seuraavien tyhjennyspäivien näyttämiseen Oma jätehuolto -palvelun tietojen perusteella. Renyyt on epävirallinen asiakassovellus, ei Renyyn tarjoama palvelu.

- Palvelu: <https://renyyt.fi/>
- Projektin repository: <https://github.com/janilahti/renyyt>
- Renyyn (Pirkanmaan Jätehuolto) virallinen sivusto: <https://renyy.fi/>
- Oma jätehuolto -palvelu: <https://renyy.fi/palvelut/oma-jatehuolto/>
- [Tekninen dokumentaatio](TECHNICAL.md)

Lyhyet käyttöohjeet: [Suomi](README.fi.md) · [English](README.en.md) · [Svenska](README.sv.md) · [Українська](README.uk.md) · [العربية](README.ar.md) · [فارسی](README.fa.md) · [Tiếng Việt](README.vi.md) · [简体中文](README.zh-Hans.md) · [Eesti](README.et.md).
README-painike avaa käyttöliittymän kielen mukaisen lyhyen ohjeen.

## Pikakäynnistys

Tarvitset Python 3.8:n tai uudemman. Peruskäyttö ei tarvitse ulkoisia Python-paketteja eikä Node.js:ää.

```bash
git clone https://github.com/janilahti/renyyt.git renyyt
cd renyyt
python3 run.py
```

Tietoja-laatikon koontiaika ja Git commit luetaan julkaisun metatiedoista. Ilman buildia ajetussa kloonissa näytetään viimeisimmän commitin ajankohta ja tunniste.

Avaa [http://127.0.0.1:18514](http://127.0.0.1:18514) ja kirjaudu Oma jätehuolto -tunnuksillasi. Palvelin kuuntelee oletuksena vain paikallisia yhteyksiä. Docker-image käyttää Python 3.13:a. OCI/GHCR-kuvan käyttö ja julkaisu kuvataan teknisessä dokumentaatiossa. Tuotannon HTTPS-, Docker-, systemd- ja proxy-ohjeet ovat teknisessä dokumentaatiossa.

Debian/Ubuntu- ja Fedora/RHEL 9+ -palvelimille on myös systemd-palvelun asentava deb/rpm-peruspaketointi. [Paketointiohje](https://github.com/janilahti/renyyt/blob/main/deploy/linux/README.md) kuvaa asennuksen, päivityksen sekä asetukset ja datan säilyttävän poiston ja erillisen täydellisen purge-siivoamisen. Web Push on valinnainen: paketti ehdottaa `python3-pywebpush`-riippuvuutta `Suggests`-määritteellä. Paketointiohje kattaa saatavuuden, vaihtoehtoisen venv-asennuksen sekä avaimet ja ajastuksen.

[APT- ja DNF-varastojen ohje](https://github.com/janilahti/renyyt/blob/main/deploy/linux/REPOSITORIES.md) kattaa allekirjoitetun GitHub Pages -pakettivaraston lisäämisen ja päivitykset suoraan paketinhallinnalla. Julkaisu vaatii ylläpitäjältä kertaluonteisen allekirjoitusavaimen ja Pagesin käyttöönoton. Päivitykset säilyttävät jo julkaistut paketit muuttumattomina; uusia paketteja lisätään ja varaston metatiedot uusitaan.

[Windows- ja macOS-paketointiselvitys](https://github.com/janilahti/renyyt/blob/main/DESKTOP-PACKAGING.md) vertailee MSI/MSIX- ja PKG/DMG-vaihtoehtoja, Pythonin sisällyttämistä sekä palvelun asennusta, päivitystä ja turvallista poistoa. Näille alustoille ei vielä julkaista omia asentajia.

Kieli ja teema pysyvät yhdessä rivittyvässä ryhmässä. Kirjautumisen painikkeet mukautuvat käytettävään tilaan: Hae tyhjennykset voi olla omalla ensimmäisellä rivillään, ja kapeammassa näkymässä painikkeet asettuvat kahteen sarakkeeseen tai yhteen pinoon.

HTTP-ohjelaatikon kopiointipainikkeet ovat käytettävissä, kun esimerkit ja upotuslinkit on muodostettu nykyisistä tunnuksista ja näkymävalinnoista.

## Tyhjennysten näyttäminen

- **Järjestys → Aikajärjestys** näyttää seuraavaksi tyhjennettävät astiat ensin.
- **Järjestys → Oma järjestys** näyttää järjestelynuolet ja vetokahvat normaalinäkymässä. Järjestys tallennetaan selaimeen. Leveässä ikkunassa säätimet ovat lisätietojen rinnalla ja väistyvät, kun lisätiedot avataan.
- **Tiivis näkymä** säilyttää valitun järjestyksen mutta piilottaa lisätiedot ja järjestelytoiminnot.
- **Astiat** valitsee näkyvät astiat. Upotus ja muistutukset perivät normaalinäkymän valinnat, ellei niille määritetä erillistä poikkeusta.
- **Vie kalenteriin (.ics)** avaa vientivaihtoehdot näkyvien astioiden seuraaville tyhjennyksille. Androidin Google Kalenteriin lisätään tapahtumat yksitellen **Lisää Google-kalenteriin** -linkeistä ja tallennetaan avautuva lomake. Muille kalentereille voi ladata `.ics`-tiedoston tai jakaa sen selaimen tuen mukaan. Latauksesta näytetään kuittaus; tiedosto löytyy selaimen latauksista. Pelkkä tiedoston avaaminen ei toimi kaikissa mobiilikalentereissa. Vienti ei päivity automaattisesti. Google-linkki lähettää Googlelle vain valitun tapahtuman otsikon ja päivän, kun linkkiä painetaan.
- **Olennaiset lisätiedot** kokoaa palvelun tiedot. Alkuperäisen API-datan voi avata erikseen.

Tyhjennyskortit erottavat tänään, huomenna ja ylihuomenna tapahtuvat tyhjennykset ennen yleistä ”tällä viikolla” -merkintää. Englannin ylihuomisen teksti on mobiiliin sopiva ”COLLECTION IN 2 DAYS”. Päivälaskurit päivittyvät vuorokauden vaihtuessa. Uusi haku tehdään seuraavan tyhjennyspäivän jälkeen tai tarvittaessa palattaessa taustalta. Epäonnistuneen haun yhteydessä voidaan näyttää selaimeen viimeksi tallennettu supistettu korttidata selvästi vanhentuneeksi merkittynä. Offline-tallennus ei sisällä koko raakaa API-vastausta eikä kimppaosakkaiden henkilötietorakenteita.

## Kielet ja saavutettavuus

Tyhjennyspillerin teksti pysyy keskitettynä myös usealle riville jakautuessaan.

Käyttöliittymässä on tarjolla seuraavat kielet: suomi (oletus), englanti, ruotsi, ukraina, arabia, persia/farsi, vietnam, yksinkertaistettu kiina ja viro (Eesti). Uusia käännöksiä on tarvittaessa helppo lisätä.

Käyttöliittymä tukee vaaleaa, tummaa ja järjestelmän teemaa, näppäimistökäyttöä, näkyvää fokusta, vähennettyä liikettä ja high-contrast-tilaa. Pitkät ohje- ja muut valintaikkunat mukautuvat mobiiliselaimen näkyvään korkeuteen ja vierivät oman ikkunansa sisällä. Taustasivun vieritys on lukittu valintaikkunan ollessa auki. Astioiden tietomerkkien reunukset pysyvät tekstin kokoisina; avattavilla tiedoilla on silti riittävä kosketusalue. Mobiilin lomakekontrollien kosketusalueet ovat vähintään 44 × 44 CSS-pikseliä; valintaruutujen alueeseen kuuluu niiden teksti.

## Tunnukset ja tietosuoja

Kirjaudu omilla Renyyn Oma jätehuolto -tunnuksillasi. Renyytissä ei luoda erillistä käyttäjätiliä. Käyttöliittymässä on lyhyt kuvaus tietojen minimoinnista ja selaimen tallennuksesta; valinnaisten muistutusten ja palautteen käsittely selitetään niiden yhteydessä.

Renyyt tarvitsee välityspalvelimen, koska Oma jätehuollon kirjautuminen käyttää eri alkuperässä olevaa cookie-istuntoa. Selain lähettää tunnukset omalle Renyyt-palvelimellesi, joka kirjautuu Renyyhyn. Palvelin ei tallenna tunnuksia levylle.

Tunnusten tallentaminen selaimeen on vapaaehtoista. **Tallenna** säilyttää ne `localStorage`ssa AES-GCM-pohjaisena sumennettuna blobina. Avain kulkee datan mukana: tämä **ei ole turvallinen salaus** eikä suojaa paikalliselta selainpääsyltä tai XSS:ltä. Älä tallenna tunnuksia jaetulla laitteella.

Salasanan näyttöpainike toimii vain käyttäjän itse kokonaan syöttämälle tai korvaamalle salasanalle, ei suoraan selaimesta palautetulle salasanalle. Turvallisuusrajat ja arkaluonteinen TRACE-lokitus kuvataan [turvallisuusohjeessa](https://github.com/janilahti/renyyt/blob/main/SECURITY.md).

## Upotus ja aloitusnäyttö

**Upotusnäkymä** näyttää vain tyhjennystiedot. Itsekseen kirjautuvan linkin voi kopioida **Näytä HTTP-kutsu → Upotus-URL** -kohdasta. Linkki kuljettaa myös astiarajauksen, järjestyksen ja tiiviin näkymän asetukset toiseen selaimeen. Tunnuksia sisältävää linkkiä on käsiteltävä salaisuutena, vaikka tunnukset ovat URL:n fragmentissa eivätkä GET-pyynnössä.

Valinnainen **Asenna**-toiminto lisää sovelluksen aloitusnäytölle. Ennen asennusta anna asiakasnumero ja salasana, valitse **Tallenna kirjautumistiedot tähän selaimeen** ja paina **Hae tyhjennykset**. Ilman tallennettuja tunnuksia painike näyttää ohjeen. Asennettu PWA käynnistyy upotusnäkymään ja voi käyttää samalla originilla tallennettuja tunnuksia. Järjestys ja muut näkymäasetukset tehdään normaalinäkymässä. Asennus vaatii tuotannossa HTTPS:n. iOS/Safarissa käytetään **Jaa → Lisää Koti-valikkoon** -toimintoa. Teknisessä dokumentaatiossa kerrotaan upotusparametreista, PWA-asetuksista ja selainvälimuistista.

## Valinnaiset toiminnot

**Muistutukset** näkyvät, kun ylläpitäjä on ottanut Web Push -tuen käyttöön ja asentanut valinnaiset push-riippuvuudet (Python-asennuksen push-extra tai natiivipaketin käyttöönotto-ohje). Palvelin säilyttää push-tilauksen ja viimeksi selaimesta synkronoidut tyhjennyspäivät, ei Renyy-tunnuksia. Palvelin ei siten voi hakea muuttuneita päiviä itsenäisesti: muistutuslista päivittyy onnistuneen selainhaun yhteydessä.

**Palaute** näkyy SMTP-asetusten ollessa käytössä. Viestin ja vapaaehtoisen vastausosoitteen lisäksi käyttäjä voi erikseen valita tyhjennystietojen liittämisen. Liite voi sisältää asiakaskohtaisia tietoja; sovellus ei lisää siihen kirjautumissalasanaa.

## Dokumentaatio

- [Tekninen dokumentaatio](TECHNICAL.md): asennus, asetukset, proxy, Docker, systemd, välimuistit ja muistutukset. Onnistuneet tyhjennystietojen haut löytyvät INFO-lokista merkinnällä `event=api_success`, joka kertoo myös tiedon lähteen ja välimuistin tilan. Caddy- ja nginx-esimerkit pysäyttävät tuntemattomat polut 404-vastaukseen jo proxylle. Niissä on myös valinnainen staattisten JS/CSS-tiedostojen ja kuvien suora jako Pythonin kuorman vähentämiseksi.
- [HTTP-rajapinta](API.md): pyynnöt, vastaukset ja virheet. **Näytä HTTP-kutsu** muodostaa myös curl-esimerkin ja tarjoaa vain selaimessa käsiteltävän JSON-tuonnin.
- [Riippuvuuksien tietoturvaseuranta](https://github.com/janilahti/renyyt/blob/main/SECURITY.md#dependency-monitoring): Dependabotin päivitys-PR:t sekä GitHubin hälytysasetusten käyttöönotto.
- [Testaus](https://github.com/janilahti/renyyt/blob/main/TESTING.md): paikalliset tarkistukset, selaintestit, kuvavertailut ja CI:n valinta. Selvästi sisäiset lokitus-, metriikka- ja Python-testimuutokset tarkistetaan ilman UI- ja selainkierrosta; rajapinta- ja HTTP-muutokset ajavat edelleen kaikki tarkistukset.
- [Muutoshistoria](CHANGELOG.md).
- [Työlista](https://github.com/janilahti/renyyt/blob/main/ROADMAP.md) ja [kehitysohjeet](https://github.com/janilahti/renyyt/blob/main/CONTRIBUTING.md).

Renyyn rajapinta on dokumentoimaton ja voi muuttua ilman ennakkovaroitusta. Käyttäjä vastaa tunnustensa turvallisesta käsittelystä ja palvelun ehtojen noudattamisesta.

Projekti on julkaistu [MIT-lisenssillä](https://opensource.org/license/mit).

Mobiilisovelluksen ja kotinäyttöwidgettien vaihtoehdot ja rajattu jatkoehdotus on
kuvattu [mobiiliselvityksessä](https://github.com/janilahti/renyyt/blob/main/MOBILE.md).
Natiivisovellusta tai widgettejä ei ole vielä toteutettu.
