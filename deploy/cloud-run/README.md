# Cloud Run

Nykyinen container sopii Cloud Run -tyyppiseen käyttöön. Cloud Run antaa portin `PORT`-ympäristömuuttujassa, jota Renyyt käyttää automaattisesti `RENYYT_PORT`in puuttuessa.

Esimerkkiasetukset:

```text
RENYYT_HOST=0.0.0.0
RENYYT_LOG_LEVEL=INFO
RENYYT_LOG_FORMAT=json
```

Docker image voidaan rakentaa esimerkiksi:

```bash
docker build -t renyyt:latest .
```

Cloud Runissa in-memory rate limiter ja prosessikohtaiset metrics-arvot ovat instanssikohtaisia. Usean instanssin deploymentissa niitä ei pidä tulkita globaaliksi tilaksi.
