# Release checklist

- [ ] Päätä julkaisu erikseen; ylläpitomuutos ei automaattisesti nosta versiota. Korota vain patch-osaa nykyisen päätöksen mukaan.
- [ ] VERSION ja CHANGELOG vastaavat julkaistavaa versiota; siirrä julkaistut Unreleased-kohdat oman version alle.
- [ ] Täysi GitHub CI on vihreä juuri julkaistavalle commitille **ennen tagia**. Käynnistä workflow käsin, jos viimeisin muutos sai vain kevyet dokumenttitarkistukset.
- [ ] Python 3.8/3.13, Ruff/coverage (78 %), ESLint/frontend, Chromium/Firefox sekä toistetut Chromium-kuvavertailut läpäisty.
- [ ] `python3 scripts/check_docs.py`, tuotantokooste ja `renyyt --check` onnistuvat.
- [ ] Asennettu wheel/lähdearkisto testataan puhtaassa ympäristössä ennen julkaisua; `/ready`, `/version` ja `/metrics/openmetrics` vastaavat odotetusti.
- [ ] `python3 scripts/check_reproducible.py` vahvistaa arkiston ja wheelin bittitarkan toistettavuuden.
- [ ] Arkisto on `renyyt-<VERSION>.tar.gz` ja sisältää ylimmän `renyyt/`-hakemiston sekä LICENSEn.
- [ ] Paketissa ei ole generoituja `.gz`-representaatioita, `.pyc`/välimuisteja, salaisuuksia tai SQLite-runtime-dataa/WAL/SHM-tiedostoja.
- [ ] Tagi vastaa täsmälleen `v$(cat VERSION)`-arvoa. `release.yml` ajaa vielä suppeamman Python/frontend/build-tarkistuksen ja julkaisee lähdearkiston; se ei odota eikä korvaa täyttä CI:tä.
- [ ] Tarkista julkaistu artifact ja julkaisuteksti. Release-workflow ei julkaise wheeliä tai natiiveja OS-asentimia.

Komennot ja CI-valinta: [TESTING.md](../TESTING.md).
