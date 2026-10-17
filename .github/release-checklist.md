# Release checklist

- [ ] `VERSION` ja `CHANGELOG.md` vastaavat toisiaan.
- [ ] Koko Python-testisarja menee läpi.
- [ ] Frontend-testit menevät läpi.
- [ ] `python3 scripts/build.py` onnistuu.
- [ ] `/ready`, `/version` ja `/metrics/openmetrics` smoke-testataan.
- [ ] Release-paketti muodostetaan `scripts/package.py`:llä.
- [ ] `python scripts/check_reproducible.py` vahvistaa release-arkiston ja wheelin bittitarkan toistettavuuden.
- [ ] Paketissa ei ole `index.html.gz`:ää, `.pyc`:tä tai `__pycache__`:a.
- [ ] Git-tag vastaa `VERSION`-tiedostoa.
- [ ] Julkaisun jälkeen artifact testataan puhtaassa hakemistossa.
