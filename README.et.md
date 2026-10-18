# Renyyt – lühijuhend

Renyyt näitab prügikastide järgmisi tühjenduspäevi Renyy (Pirkanmaan Jätehuolto) Oma jätehuolto teenuse andmetest. See on mitteametlik kliendirakendus.

Teenus: <https://renyyt.fi/>. Oma serveri jaoks on vaja Python 3.8 või uuemat: paki väljalaske arhiiv lahti, käivita selle kaustas `python3 run.py` ja ava <http://127.0.0.1:8787>.

## Põhikasutus

- Vali keel, sisesta Oma jätehuolto kliendinumber ja parool ning vajuta **Laadi tühjendused**.
- **Prügikastid** määrab nähtavad kastid. **Järjestus → Oma järjestus** võimaldab tavavaates liigutada kaste nooltega või lohistades. **Kompaktne vaade** säilitab järjestuse ilma muutmisnuppudeta.
- Ekspordi järgmised tühjendused `.ics`-kalendrisse. **Põimitud vaade** näitab ainult tühjendusandmeid. Paigaldamine, tagasiside ja meeldetuletused sõltuvad serveri seadetest ning brauseri toest. Paigaldamiseks peavad kliendinumber ja parool olema salvestatud. Sisesta need, vali sisselogimisandmete salvestamine selles brauseris ja vajuta „Laadi tühjendused”. Androidis lisa tühjendused Google Kalendrisse ükshaaval ekspordiakna linkidega. Eksporditud sündmused ei uuene automaatselt.

Sisselogimisandmete salvestamine on vabatahtlik. Brauseri andmeplokk ei ole turvaline krüpteerimine; ära salvesta andmeid jagatud seadmes ega jaga neid sisaldavaid põimitud vaate linke. Meeldetuletused põhinevad viimasel edukal brauseripäringul. Vanad salvestatud andmed märgitakse aegunuks.

Lisateave: [põhijuhend (soome)](README.md), [paigaldus ja seaded (soome)](TECHNICAL.md), [API (soome)](API.md), [muudatused (inglise)](CHANGELOG.md), [testimine (inglise)](https://github.com/janilahti/renyyt/blob/main/TESTING.md).
