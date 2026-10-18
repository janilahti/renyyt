# systemd + nginx

Tyypillinen tuotantomalli on `Internet → nginx :443 → 127.0.0.1:8787 → Renyyt`.
Pidä Python localhostissa ja anna nginxin hoitaa TLS sekä gzip/Brotli.

Asennus, virtuaaliympäristö ja oikeudet kuvataan [teknisessä ohjeessa](../../TECHNICAL.md).
Molemmat systemd-palvelut käyttävät `/opt/renyyt/venv/bin/renyyt`-asennusta,
samaa `/etc/renyyt/renyyt.env`-tiedostoa ja pysyvää `/var/lib/renyyt`-tilahakemistoa.
Sovelluskoodi ei tarvitse palvelun kirjoitusoikeuksia. Päivitys ja tuotantokooste
tehdään ylläpitäjän toimesta ennen uudelleenkäynnistystä.

[Nginx-esimerkki](../nginx/renyyt.conf.example) on TLS-server-lohkoon lisättävä
katkelma, ei kokonainen nginx.conf. Se säilyttää `/renyyt`-etuliitteen:
aseta `RENYYT_BASE_PATH=/renyyt` ja `RENYYT_TRUSTED_PROXIES=127.0.0.1`
(tai todellinen proxy-IP). Host ja X-Forwarded-Host säilyttävät myös portin.
[Caddy-esimerkki](../caddy/Caddyfile.example) riisuu etuliitteen, joten jätä
`RENYYT_BASE_PATH` silloin tyhjäksi.

Muistutusten timer edellyttää push-extraa ja VAPID-asetuksia. Pidä sisäinen
scheduler pois päältä, kun timer on käytössä. Muuta timerin 07/18-kellonajat
palvelimen aikavyöhykkeen ja toivottujen lähetyshetkien mukaisiksi. Sama
SQLite-polku ja käyttäjä tarvitaan sekä HTTP-palvelulle että timerille.

Kopioi halutut `.example`-yksiköt `/etc/systemd/system/`-hakemistoon ilman
`.example`-päätettä ja suorita `systemctl daemon-reload`. Käynnistä HTTP-palvelu
`systemctl enable --now renyyt.service` ja tarvittaessa ulkoinen scheduler
`systemctl enable --now renyyt-reminders.timer`. Tarkista lokit `journalctl -u renyyt`.
