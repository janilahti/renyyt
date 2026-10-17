# systemd + nginx

Tyypillinen tuotantomalli on:

```text
Internet -> nginx :443 -> 127.0.0.1:8787 -> Renyyt
```

Pidä Renyyt sidottuna localhostiin ja anna nginxin hoitaa TLS sekä gzip/Brotli. Jos nginx välittää `/renyyt`-prefixin upstreamille, aseta `RENYYT_BASE_PATH=/renyyt`. Lisää nginxin loopback-osoite `RENYYT_TRUSTED_PROXIES`-asetukseen ennen kuin luotat `X-Forwarded-*`-otsakkeisiin.
