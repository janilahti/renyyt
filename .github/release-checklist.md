# Release checklist

- [ ] Päätä julkaisu erikseen; ylläpitomuutos ei automaattisesti nosta versiota. Versio 1.0.1 on erikseen hyväksytty; sen jälkeen oletus on patch-korotus.
- [ ] VERSION ja CHANGELOG vastaavat julkaistavaa versiota; siirrä julkaistut Unreleased-kohdat oman version alle.
- [ ] Täysi GitHub CI on vihreä juuri julkaistavalle commitille **ennen tagia**. Käynnistä workflow käsin, jos viimeisin muutos sai vain kevyet dokumenttitarkistukset.
- [ ] Python 3.8/3.13, Ruff/coverage (78 %), ESLint/frontend, Chromium/Firefox sekä toistetut Chromium-kuvavertailut läpäisty.
- [ ] `python3 scripts/check_docs.py`, tuotantokooste ja `renyyt --check` onnistuvat.
- [ ] Asennettu wheel/lähdearkisto testataan puhtaassa ympäristössä ennen julkaisua; `/ready`, `/version` ja `/metrics/openmetrics` vastaavat odotetusti.
- [ ] `python3 scripts/check_reproducible.py` vahvistaa tar.gz/ZIP-arkistojen ja wheelin bittitarkan toistettavuuden.
- [ ] Arkistot ovat `renyyt-<VERSION>.tar.gz` ja `renyyt-<VERSION>.zip`, sisältävät kaikki kielikohtaiset README-ohjeet, ja molemmissa on ylin `renyyt/`-hakemisto sekä LICENSE.
- [ ] Paketissa ei ole generoituja `.gz`-representaatioita, `.pyc`/välimuisteja, salaisuuksia tai SQLite-runtime-dataa/WAL/SHM-tiedostoja.
- [ ] Tagi vastaa täsmälleen `v$(cat VERSION)`-arvoa. `release.yml` ajaa vielä suppeamman Python/frontend/build-tarkistuksen ja julkaisee tar.gz/ZIP-arkistot sekä deb/rpm-peruspaketit ja SHA256SUMS-tiedoston; se ei odota eikä korvaa täyttä CI:tä.
- [ ] Tarkista julkaistu artifact ja julkaisuteksti. Release-workflow julkaisee myös OCI-kuvan GHCR:ään; wheeliä tai Windows/macOS-asentimia ei julkaista.

Komennot ja CI-valinta: [TESTING.md](../TESTING.md).

- [ ] Natiivien deb/rpm-pakettien toistettavuus, jakelumatriisi ja systemd-asennus/päivitys/remove/purge ovat vihreät. Tarkista myös säilyvän purge-komennon siivous sekä pakettien SHA256SUMS.

## Native release assets

Packaging supports numeric x.y.z versions. The tag workflow attaches tar.gz, ZIP,
deb/all, rpm/noarch and SHA256SUMS after native lifecycle checks pass. These are
downloadable packages, not apt/dnf repositories. Before every tag, update VERSION
and dated changelog notes and validate the final release commit with full CI.
Windows/macOS, native mobile apps and signed package repositories remain optional
follow-up scope, not requirements for this release.

- [ ] GHCR-version ja latest-tagin kohteet/digestit ovat oikein; ensimmäisellä julkaisulla tarkista paketin julkisuus ja anonyymi pull.
