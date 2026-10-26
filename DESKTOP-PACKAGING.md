# Renyyt Windowsissa ja macOS:ssa: paketointiselvitys

Selvitetty 26.10.2026. Tämä on toteutussuositus, ei ilmoitus valmiista tai
alustoilla testatusta paketoinnista. Nykyiset Linux-paketit säilyvät ennallaan.

## Suositus

Renyyt kannattaa paketoida edelleen pieneksi paikalliseksi web-palveluksi.
Sama selainkäyttöliittymä avataan osoitteessa `http://127.0.0.1:18514/`.
Electronia, omaa selainmoottoria tai uutta työpöytäkäyttöliittymää ei tarvita.
Valmiin palvelun käyttäjälle nykyinen URL/PWA riittää jo nyt; uusi paketti on
tarpeellinen nimenomaan oman Renyyt-palvelimen asentajalle.

Suosittelen ensimmäiseksi Windowsin MSI-pakettia, sitten macOS:n allekirjoitettua
ja notarisoitua PKG-pakettia. Molempiin sisällytetään yksityinen Python 3.13
tuettuine korjauspäivityksineen. Käyttäjän ei tarvitse asentaa Pythonia eikä
paketti muuta koneen muuta Python-asennusta. Linuxissa jatketaan jakelun Pythonilla.

| Asia | Windows | macOS |
| --- | --- | --- |
| Ensisijainen asennusmuoto | MSI, esimerkiksi WiX-työkaluilla | Flat PKG, Applen paketointityökaluilla |
| Palvelun valvonta | Windows Service Control Manager ja erikseen arvioitu palvelusovitin | launchd / LaunchDaemon |
| Python | Yksityinen, sovelluksen mukana | Yksityinen, sovelluksen mukana |
| Ensimmäinen arkkitehtuuri, ehdotus | x64 | Apple Silicon arm64 |
| Seuraava arkkitehtuuri | ARM64 tarpeen ja testikoneiden mukaan | Intel x86_64 tarpeen ja OS-tuen mukaan |
| Tavallinen poisto | Ohjelma ja palvelu pois; asetukset/data säilyvät | Oma poistotyökalu; asetukset/data säilyvät |
| Täysi siivous | Erillinen purge-toiminto | Erillinen purge-toiminto |

Käyttöjärjestelmien vähimmäisversiot ja arkkitehtuurit ovat vielä päätettäviä.
Ehdotus aloittaa ylläpidetystä Windows 11:stä ja tuetuista macOS-versioista;
Windows Serverin sekä Intel-Macin lupaaminen vaatii oman testauksen.

## Miksi MSI eikä ensin MSIX?

MSI sopii palvelimena asennettavan ohjelman elinkaareen: asennus, päivitys,
palvelun käynnistys/pysäytys ja poisto voidaan määritellä saman asennuspaketin
sisälle. Windows Installerissa on palvelujen ja tiedostojen hallintaan valmiit
toiminnot. Tavoite on käyttää niitä ja minimoida ylläpitäjän oikeuksilla ajettava
oma asennuskoodi. [Microsoftin toimintoluettelo](https://learn.microsoft.com/en-us/windows/win32/msi/standard-actions-reference).

MSIX voi myös sisältää palveluja; se ei ole teknisesti mahdoton vaihtoehto.
Palvelutuki kuitenkin rajaa kohdejärjestelmät ja vaatii ylläpitäjän oikeudet,
ja pakettien täytyy olla allekirjoitettuja ja luotettuja kohdekoneessa. Sen
erityisrajoitteet eivät tuo tässä ensimmäisessä palvelinpaketissa selvää etua.
MSIX kannattaa arvioida uudelleen, jos tavoitteeksi tulee ensisijaisesti
Microsoft Store / käyttäjäkohtainen työpöytäsovellus.
[MSIX-palvelujen tuetut kohteet](https://learn.microsoft.com/en-us/windows/msix/desktop/managing-your-msix-deployment-targetdevices),
[allekirjoitusvaatimukset](https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview).

Python-ohjelman käynnistämistä ei voi vain kirjata palveluksi ja olettaa sen
toimivan. Renyytin nykyinen `server.main()` palvelee konsoliprosessina ja käsittelee
SIGTERM-signaalia; Windows-palvelun ohjaus ja siisti pysäytys vaativat sovittimen.
WinSW on yksi tutkittava vaihtoehto, ei tässä päätetty uusi riippuvuus.
Sovittimen, käyttöoikeuksien ja version on oltava ylläpidettyjä ja testattuja.
Pysäytyksen tulee sulkea palvelin ja muistutustyöt hallitusti; ei normaalitilanteessa
pakotettua prosessin tappamista tai uutta julkista HTTP-pysäytysrajapintaa.
[WinSW:n oma dokumentaatio](https://github.com/winsw/winsw).

## Python mukaan: vaihtoehdot ja ylläpitovastuu

Windowsin virallinen CPython embeddable ZIP on tarkoitettu sovelluksen mukana
jaettavaan yksityiseen Pythoniin. Se on hyvä ensimmäinen vertailukohta: Renyytin
peruspalvelin ei tarvitse ulkoisia Python-kirjastoja. Pakettiin kuuluvat eristetty
hakupolku, Renyytin resurssit ja tarvittavat lisenssit. Myös CPythonin vaatiman
Microsoft C -ajoympäristön saatavuus varmistetaan kohdekoneessa. Pip ei kuulu tämän
jakelutavan normaaliin loppukäyttäjän päivitysmalliin; mahdolliset lisäkirjastot
rakennetaan pakettiin hallitusti.
[CPythonin Windows-jakelut](https://docs.python.org/3.13/using/windows.html#the-embeddable-package).

Toinen vaihtoehto on PyInstallerin `onedir` molemmille alustoille. Se kerää
sovelluksen, Pythonin ja riippuvuudet yhteen hakemistoon. Tämä yhdenmukaistaa
rakennusta ja on macOS:ssa vahva ehdokas. `onefile`-mallia en valitsisi
taustapalvelulle: se purkaa sisältöään väliaikaishakemistoon käynnistettäessä,
ja asennuspaketti huolehtii joka tapauksessa monen tiedoston jakelusta.
Valinta embeddable/PyInstaller ratkaistaan pienellä rakennuskokeella; suositukseni
on Windowsissa embeddable ensin ja macOS:ssa PyInstaller `onedir`.
[PyInstallerin toimintamalli](https://pyinstaller.org/en/stable/operating-mode.html).

Bundlattu Python tuo uuden vastuun: sen ja esimerkiksi OpenSSL:n
tietoturvakorjaukset tulevat Renyyt-päivityksen mukana. Pelkkä käyttöjärjestelmän
päivitys ei päivitä yksityistä tulkkia. Rakennuksessa kirjataan tarkat versiot,
lähteet ja tarkistussummat sekä julkaistaan komponenttiluettelo ja lisenssit.
Python 3.8+ säilyy lähdekoodin/Linuxin yhteensopivuusvaatimuksena; sitä ei
tarvitse toimittaa uusien työpöytäpakettien tulkkina.

Web Push pidetään ensimmäisessä paketissa pois käytöstä tai omana myöhemmin
testattavana pakettivarianttinaan. MSI/PKG ei tarjoa apt/dnf:n `Suggests`-mallia
sellaisenaan. Käyttäjää ei ohjata asentamaan pipillä koneen yleiseen Pythoniin.
Jos muistutusten nimetyt aikavyöhykkeet otetaan Windowsissa mukaan, tarvitaan myös
IANA-aikavyöhyketiedot, käytännössä esimerkiksi paketoitu `tzdata`.
[Pythonin zoneinfo ja Windows](https://docs.python.org/3.13/library/zoneinfo.html#data-sources).

## macOS: PKG, launchd ja poisto

PKG sopii järjestelmätason palvelimeen: se asentaa sovelluksen ja launchd-määrityksen
hallittuihin paikkoihin. DMG on jakelusäiliö eikä ratkaise palvelun asennusta tai
poistoa itsessään. Sen voisi lisätä myöhemmin, jos syntyy vetämällä asennettava
`.app` tai käynnistys-/hallintasovellus; palvelimen ensimmäiselle paketille siitä
ei ole olennaista lisähyötyä.
[Applen jakelumuodot](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution).

Koko koneen jatkuva palvelu tarvitsee LaunchDaemonin, joka ajaa varsinaisen
palvelimen rajatuilla oikeuksilla. LaunchAgent sopii eri käyttötapaukseen: vain
kirjautuneelle käyttäjälle ajettavaan palveluun. Agenttia ei pidä luvata
ympärivuorokautiseksi palvelimeksi, ja nukkuva kone ei muutu asennuksen avulla
aina saatavaksi palvelimeksi.
[Applen launchd-ohje](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).

PKG-asennuksen vastineeksi tarvitaan oma poistotyökalu. Pelkkä pakettikuitin
unohtaminen `pkgutil --forget` -komennolla ei ole ohjelmatiedostojen poisto.
Poisto pysäyttää launchd-palvelun ja poistaa vain paketin omistamat tiedostot.
Tavallinen poisto säilyttää asetukset ja mahdollisen tietokannan; purge poistaa
ne erillisellä, tietoisella toimenpiteellä. Aiemmin olemassa ollutta käyttäjää,
ryhmää, hakemistoa tai ylläpitäjän muuta sisältöä ei saa ottaa omistukseen eikä
poistaa. Myös pakettikuitti ja mahdollinen oma palvelutunnus käsitellään oikein.
Applen oma poistoesimerkki erottaa tiedostojen poiston pakettikuitin poistosta:
[Command Line Tools -paketin poistaminen](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools).

Luonteva ehdotus tiedostojen sijoitteluun on ohjelmalle oma hakemisto
`/Library/Application Support/Renyyt/` ja erilliset, oikeuksiltaan rajatut
asetukset sekä kirjoitettava tilahakemisto. Tarkat polut päätetään ennen toteutusta;
käyttäjäkohtaiset ja koko koneen asennukset eivät saa sekoittua.

## Luottamus, päivitykset ja turvallinen oletus

macOS-julkaisu tarvitsee ohjelmakoodille Developer ID Application -allekirjoituksen,
PKG:lle Developer ID Installer -allekirjoituksen sekä notarisaation ja lipukkeen
kiinnityksen. Varmenteet edellyttävät Apple Developer -jäsenyyttä. Windowsissa
tuotantoasentaja ja omat suoritettavat tiedostot allekirjoitetaan luotetulla
Authenticode-ratkaisulla ja aikaleimataan; itse allekirjoitettu testivarmenne ei
ole vastaava käyttäjäkokemus. Allekirjoitus ei ole lupaus SmartScreen-varoitusten
täydellisestä poistumisesta. Sertifikaatit, tilit ja mahdolliset kustannukset
ratkaisee ylläpitäjä ennen julkaisua.
[Apple Developer ID](https://developer.apple.com/help/glossary/developer-id-certificate/),
[notarisaatio](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[Microsoftin SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
ja [Authenticode-aikaleimaus](https://learn.microsoft.com/en-us/windows/win32/seccrypto/time-stamping-authenticode-signatures).
Myös asentajan rakennustyökalun lisenssi ja mahdollinen maksu tarkistetaan ennen
työkaluvalintaa; WiX on tässä esimerkki, ei tehty hankintapäätös.

Ensimmäinen päivitysmalli on uuden allekirjoitetun asennuspaketin ajo GitHub
Releasesista. Ei omaa taustalla oikeuksin lataavaa päivityspalvelua. Päivitys
säilyttää muokatun konfiguraation, portin, palveluidentiteetin ja datan sekä
pysäyttää vanhan prosessin ennen tiedostojen vaihtoa. Winget/Homebrew ovat
myöhempiä jakelukanavia, eivät edellytys ensimmäiselle paketille.

Oletus pysyy `127.0.0.1:18514`:ssä. Asennus ei avaa palomuuria tai lähiverkkoa
automaattisesti. Ulkoinen palvelu vaatii saman harkitun HTTPS/reverse proxy
-asetuksen kuin nykyinen asennus. Oma jätehuolto -tunnuksia ei pyydetä
asentajassa eikä tallenneta palvelimelle; nykyinen selainmalli säilyy.

## Mitä repossa oikeasti puuttuu?

Lähdekoodin katselmoinnissa löytyivät seuraavat toteutustarpeet:

- Nykyiset `package_linux.py`, systemd- ja purge-rutiinit ovat Linux-kohtaisia.
  Niitä ei voi käyttää Windows/macOS-asentajana sellaisenaan.
- `server.py` löytää resurssit lähdepuusta tai `sys.prefix/share/renyyt`-polusta.
  Bundlattu asennus tarvitsee testatun resurssipolun, esimerkiksi eksplisiittisen
  `RENYYT_DATA_ROOT`-asetuksen. Se ohjaa resursseja ja myös
  tietokannan oletussijaintia, joten `RENYYT_REMINDERS_DB` määritellään erikseen
  kirjoitettavaan tilahakemistoon.
- Nykyiset oletuspolut muistutustietokannalle ovat Unix-painotteisia. Asetukset,
  SQLite ja lokit erotetaan kirjoitussuojatusta ohjelmasta: Windowsissa esimerkiksi
  `%ProgramFiles%` ja ACL-rajattu `%ProgramData%`, macOS:ssa vastaavat omat polut.
- Palvelun pysäytys ja virhetilat testataan Windowsin ohjaustapahtumilla ja
  macOS:n SIGTERM/launchd-elinkaarella. Taustapalvelu ei avaa selainta käyttäjän
  istuntoon; selaimen avaus on käyttäjän erillinen pikakuvake/toiminto.
- HTTPS-varmenteiden toiminta, Unicode/välilyönnit poluissa, localhost,
  aikavyöhykkeet ja DST sekä suojattujen asetusten käyttöoikeudet testataan
  oikeassa paketoidussa prosessissa, ei vain kehittäjän Pythonissa.

## Toteutusjärjestys ja hyväksymiskriteerit

1. Sovitaan palvelin/käyttäjäkohtainen laajuus, ensimmäiset käyttöjärjestelmät
   ja arkkitehtuurit sekä allekirjoitustilit. Suositus: järjestelmätason palvelin,
   ylläpidetty Windows 11 x64 ja macOS arm64 ensin.
2. Tehdään Windows/macOS-CI:hin sovelluksen käynnistys, `--check`, `/health` ja
   `/ready` sekä siisti pysäytys. Tehdään pieni bundlauskoe ilman asennusta.
   Tämä selvittää polku- ja tulkkivalinnan ennen asentajan toteuttamista.
3. Toteutetaan MSI ja palvelusovitin; testataan asennus → käynnistys → päivitys
   → poisto → uudelleenasennus → purge kertakäyttöisellä Windows-runnerilla.
4. Toteutetaan PKG, launchd ja poistotyökalu vastaavilla macOS-testeillä.
5. Lisätään tuotantoallekirjoitus/notarisaatio suojattuun julkaisuputkeen.
   PR:t käyttävät testivarmenteita eivätkä saa julkaisuavaimia. Tarkistetaan
   allekirjoitukset myös lopullisesta ladattavasta paketista.

Molemmilla alustoilla testataan myös epäonnistunut asennus/päivitys ja palautuminen,
portin varaus, olemassa olevien tiedostojen ja tunnusten säilyminen, rajoitetut
oikeudet sekä poiston jälkeen jäävät palvelut/ajastukset/tiedostot. Tarkistussummien
ja rakennuksen toistettavuus arvioidaan erikseen: aikaleimattu allekirjoitus ja
Applen notarisaatio eivät ole sama asia kuin tavutarkasti toistettava
allekirjoittamaton sisältö.

PyInstaller-rakennus tehdään kohdealustalla; nykyinen Ubuntu-CI ei yksin riitä.
GitHubin Windows- ja macOS-runnerit mahdollistavat automaation, mutta palveluiden
ja käyttöjärjestelmän oman varoituskäyttöliittymän toiminta varmistetaan myös
oikealla kohdekoneella ennen tukilupausta.
[PyInstallerin alustarajat](https://pyinstaller.org/en/stable/).

Seuraava järkevä rajattu toteutustyö olisi alustakohtainen CI/bundlauskoe.
Varsinaisia asentajia, palvelusovittimia tai allekirjoitusratkaisuja ei ole tällä
selvityksellä lisätty eikä valittu julkaistaviksi.
