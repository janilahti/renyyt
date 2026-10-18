# Renyyt – seuraavat tyhjennykset

Kevyt, itse ylläpidettävä web-käyttöliittymä ja Python-välityspalvelin Pirkanmaan Jätehuollon **Renyyn Oma jätehuolto** -palvelun jäteastioiden tyhjennyspäiville. Renyyt on epävirallinen asiakassovellus, ei Renyyn tai Pirkanmaan Jätehuollon tuote.

- [Projektin repository](https://github.com/janilahti/renyyt)
- [Renyyn virallinen sivusto](https://renyy.fi/)
- [Oma jätehuolto -palvelu](https://renyy.fi/palvelut/oma-jatehuolto/)

## Pikakäynnistys

Tarvitset Python 3.8:n tai uudemman. Peruskäyttö ei tarvitse ulkoisia Python-paketteja eikä Node.js:ää.

```bash
git clone https://github.com/janilahti/renyyt.git renyyt
cd renyyt
python3 run.py
```

Avaa [http://127.0.0.1:8787](http://127.0.0.1:8787) ja kirjaudu Oma jätehuolto -tunnuksillasi. Palvelin kuuntelee oletuksena vain paikallisia yhteyksiä. Docker-kuva käyttää Python 3.13:a. Tuotannon HTTPS-, Docker-, systemd- ja proxy-ohjeet ovat teknisessä dokumentaatiossa.

## Tyhjennysten näyttäminen

- **Järjestys → Aikajärjestys** näyttää seuraavaksi tyhjennettävät astiat ensin.
- **Järjestys → Oma järjestys** näyttää järjestelynuolet ja vetokahvat normaalinäkymässä. Järjestys tallennetaan selaimeen. Leveässä ikkunassa säätimet ovat lisätietojen rinnalla ja väistyvät, kun lisätiedot avataan.
- **Tiivis näkymä** säilyttää valitun järjestyksen mutta piilottaa lisätiedot ja järjestelytoiminnot.
- **Astiat** valitsee näkyvät astiat. Upotus ja muistutukset perivät normaalinäkymän valinnat, ellei niille määritetä erillistä poikkeusta.
- **Vie kalenteriin (.ics)** vie näkyvien astioiden seuraavat tyhjennykset kalenteriin.
- **Olennaiset lisätiedot** kokoaa palvelun tiedot. Alkuperäisen API-datan voi avata erikseen.

Päivälaskurit päivittyvät vuorokauden vaihtuessa. Uusi haku tehdään seuraavan tyhjennyspäivän jälkeen tai tarvittaessa palattaessa taustalta. Epäonnistuneen haun yhteydessä voidaan näyttää selaimeen viimeksi tallennettu supistettu korttidata selvästi vanhentuneeksi merkittynä. Offline-tallennus ei sisällä koko raakaa API-vastausta eikä kimppaosakkaiden henkilötietorakenteita.

## Kielet ja saavutettavuus

Kielet ovat suomi (oletus), englanti, ruotsi, ukraina, arabia, persia/farsi, vietnam ja yksinkertaistettu kiina. Arabia ja persia käyttävät oikealta vasemmalle kulkevaa asettelua. Persian tyhjennyspäivät käyttävät gregoriaanista kalenteria persialaisin numeroin.

Käyttöliittymä tukee vaaleaa, tummaa ja järjestelmän teemaa, näppäimistökäyttöä, näkyvää fokusta, vähennettyä liikettä ja high-contrast-tilaa. Mobiilin lomakekontrollien kosketusalueet ovat vähintään 44 × 44 CSS-pikseliä; valintaruutujen alueeseen kuuluu niiden teksti.

## Tunnukset ja tietosuoja

Renyyt tarvitsee välityspalvelimen, koska Oma jätehuollon kirjautuminen käyttää eri alkuperässä olevaa cookie-istuntoa. Selain lähettää tunnukset omalle Renyyt-palvelimellesi, joka kirjautuu Renyyhyn. Palvelin ei tallenna tunnuksia levylle.

Tunnusten tallentaminen selaimeen on vapaaehtoista. **Tallenna** säilyttää ne `localStorage`ssa AES-GCM-pohjaisena sumennettuna blobina. Avain kulkee datan mukana: tämä **ei ole turvallinen salaus** eikä suojaa paikalliselta selainpääsyltä tai XSS:ltä. Älä tallenna tunnuksia jaetulla laitteella.

Salasanan näyttöpainike toimii vain käyttäjän itse kokonaan syöttämälle tai korvaamalle salasanalle, ei suoraan selaimesta palautetulle salasanalle. Turvallisuusrajat ja arkaluonteinen TRACE-lokitus kuvataan [turvallisuusohjeessa](https://github.com/janilahti/renyyt/blob/main/SECURITY.md).

## Upotus ja aloitusnäyttö

**Upotusnäkymä** näyttää vain tyhjennystiedot. Itsekseen kirjautuvan linkin voi kopioida **Näytä HTTP-kutsu → Upotus-URL** -kohdasta. Linkki kuljettaa myös astiarajauksen, järjestyksen ja tiiviin näkymän asetukset toiseen selaimeen. Tunnuksia sisältävää linkkiä on käsiteltävä salaisuutena, vaikka tunnukset ovat URL:n fragmentissa eivätkä GET-pyynnössä.

Valinnainen **Asenna**-toiminto lisää sovelluksen aloitusnäytölle. Asennettu PWA käynnistyy upotusnäkymään ja voi käyttää samalla originilla tallennettuja tunnuksia. Järjestys ja muut näkymäasetukset tehdään normaalinäkymässä. Asennus vaatii tuotannossa HTTPS:n. iOS/Safarissa käytetään **Jaa → Lisää Koti-valikkoon** -toimintoa. Teknisessä dokumentaatiossa kerrotaan upotusparametreista, PWA-asetuksista ja selainvälimuistista.

## Valinnaiset toiminnot

**Muistutukset** näkyvät, kun ylläpitäjä on ottanut Web Push -tuen käyttöön ja asentanut push-extran. Palvelin säilyttää push-tilauksen ja viimeksi selaimesta synkronoidut tyhjennyspäivät, ei Renyy-tunnuksia. Palvelin ei siten voi hakea muuttuneita päiviä itsenäisesti: muistutuslista päivittyy onnistuneen selainhaun yhteydessä.

**Palaute** näkyy SMTP-asetusten ollessa käytössä. Viestin ja vapaaehtoisen vastausosoitteen lisäksi käyttäjä voi erikseen valita tyhjennystietojen liittämisen. Liite voi sisältää asiakaskohtaisia tietoja; sovellus ei lisää siihen kirjautumissalasanaa.

## Dokumentaatio

- [Tekninen dokumentaatio](TECHNICAL.md): asennus, asetukset, proxy, Docker, systemd, välimuistit ja muistutukset.
- [HTTP-rajapinta](API.md): pyynnöt, vastaukset ja virheet. **Näytä HTTP-kutsu** muodostaa myös curl-esimerkin ja tarjoaa vain selaimessa käsiteltävän JSON-tuonnin.
- [Testaus](https://github.com/janilahti/renyyt/blob/main/TESTING.md): paikalliset tarkistukset, selaintestit, kuvavertailut ja CI:n valinta.
- [Muutoshistoria](CHANGELOG.md).
- [Työlista](https://github.com/janilahti/renyyt/blob/main/ROADMAP.md) ja [kehitysohjeet](https://github.com/janilahti/renyyt/blob/main/CONTRIBUTING.md).

Upstream-rajapinta on dokumentoimaton ja voi muuttua ilman ennakkovaroitusta. Käyttäjä vastaa tunnustensa turvallisesta käsittelystä ja palvelun ehtojen noudattamisesta.

Projekti on julkaistu [MIT-lisenssillä](https://opensource.org/license/mit).
