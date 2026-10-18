# Renyyt – pikaohje

Renyyt näyttää Renyyn (Pirkanmaan Jätehuolto) Oma jätehuolto -palvelun seuraavat jäteastioiden tyhjennyspäivät. Se on epävirallinen asiakassovellus.

Palvelu: <https://renyyt.fi/>. Oman palvelimen käynnistys vaatii Python 3.8:n tai uudemman: pura julkaisupaketti ja suorita sen hakemistossa `python3 run.py`. Avaa <http://127.0.0.1:8787>.

## Peruskäyttö

- Valitse kieli ja kirjaudu Oma jätehuolto -asiakasnumerolla ja salasanalla. Paina **Hae tyhjennykset**.
- **Astiat** rajaa näkyvät astiat. **Järjestys → Oma järjestys** sallii siirtämisen nuolilla tai vetämällä normaalinäkymässä. **Tiivis näkymä** säilyttää järjestyksen mutta piilottaa järjestelyn.
- Kalenterivienti tallentaa seuraavat tyhjennykset `.ics`-tiedostoon. **Upotusnäkymä** näyttää vain tyhjennystiedot. Asennus, palaute ja muistutukset ovat käytettävissä palvelimen ja selaimen tuen mukaan.

Tunnusten tallennus on vapaaehtoista. Selaimen tunnusblob ei ole turvallinen salaus; älä tallenna tunnuksia jaetulla laitteella äläkä jaa niitä sisältäviä upotuslinkkejä. Muistutukset perustuvat viimeiseen onnistuneeseen selainhakuun. Vanha tallennettu data merkitään vanhentuneeksi.

Lisätiedot: [laajempi käyttöohje](README.md), [asennus ja asetukset](TECHNICAL.md), [API](API.md), [muutokset](CHANGELOG.md), [testaus](https://github.com/janilahti/renyyt/blob/main/TESTING.md).
