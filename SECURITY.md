# Security policy

This project proxies authentication to an external waste-management service and may handle credentials and customer-specific data.

Do not include real credentials, customer numbers, addresses, API responses or embed URLs containing passwords in public issues or logs.

For a public repository, configure a private security-reporting channel (for example GitHub private vulnerability reporting) before inviting external reports. Until such a channel is configured, security-sensitive findings should not be posted publicly.

Saved browser credentials are stored as an AES-GCM-based obscured blob whose key is stored alongside the data. This reduces accidental clear-text exposure but is not secure encryption against local browser access or XSS.


## TRACE-diagnostiikka

`RENYYT_LOG_LEVEL=TRACE` on tarkoituksella arkaluonteinen vianetsintätila. Se voi kirjoittaa lokiin Renyy-tunnuksia ja salasanoja, asiakasnumeroita, Renyyt/Oma jätehuolto -JSON-pyyntöjä ja -vastauksia, SMTP-tunnuksia, palautteen sisältöä sekä SMTP-vastauksia. Upstreamin HTML- tai JavaScript-sisältöä ei tarkoituksella kirjata. Älä käytä TRACEa normaalissa tuotantokäytössä. Suojaa TRACE-lokit, älä lähetä niitä sellaisenaan eteenpäin ja poista ne vianetsinnän jälkeen. Tavallinen `DEBUG` on suunniteltu siten, ettei näitä tietoja kirjata.


Palvelinmuistivälimuisti säilyttää aktivoituna onnistuneita asiakaskohtaisia JSON-vastauksia vain prosessin RAM-muistissa TTL:n ajan. Cache-avaimessa tunnukset korvataan prosessikohtaisella HMAC-tiivisteellä, mutta itse vastausdata on muistissa selväkielisenä prosessin käytettävissä; tämän vuoksi cachea ei pidä aktivoida ympäristössä, jossa prosessin muistieristykseen ei luoteta. Välimuisti voi lisäksi palvella aiemmin onnistuneen vastauksen samoilla tunnuksilla TTL:n loppuun asti, vaikka upstream-salasana olisi sillä välin vaihdettu, joten turvallisuuskriittisessä käytössä TTL pidetään lyhyenä tai cache poistetaan käytöstä.

## Palautteen tyhjennystietoliite

Palautelomakkeen tyhjennystietoliite on aina käyttäjän erikseen valittava. Liite sisältää UI:ssa parhaillaan olevan Renyyt-JSON-datan ja voi sisältää asiakasnumeroita tai muita asiakaskohtaisia jätehuoltotietoja. Kirjautumistunnuksia ja salasanaa ei lisätä liitteeseen sovelluksen toimesta. Liitettä ei tallenneta palvelimelle; se välitetään SMTP-viestin liitteenä.

## Web Push -muistutukset

Web Push on valinnainen ominaisuus. Palvelimelle ei tallenneta Renyy-kirjautumistunnuksia muistutuksia varten. SQLite-store sisältää kuitenkin selaimen push-endpointin ja subscription-avaimet, joita on käsiteltävä salaisena capability-datana, sekä asiakaskohtaisia tyhjennyspäiviä ja palvelun/jätelajin nimiä. Tietokantatiedoston käyttöoikeudet ja varmuuskopiot on suojattava vastaavasti. Käyttäjä ottaa ilmoitukset erikseen käyttöön selaimessa; ilmoituslupaa ei pyydetä automaattisesti sivulatauksella.
