# Renyyt – snabbguide

Renyyt visar kommande tömningsdagar för avfallskärl från Renyys (Pirkanmaan Jätehuolto) tjänst Oma jätehuolto. Det är en inofficiell klient.

Tjänst: <https://renyyt.fi/>. För egen drift behövs Python 3.8 eller senare: packa upp utgåvan, kör `python3 run.py` i katalogen och öppna <http://127.0.0.1:8787>.

## Grundläggande användning

1. Välj språk, ange kundnummer och lösenord för Oma jätehuolto och tryck på **Hämta tömningar**.
2. **Kärl** väljer vilka kärl som visas. **Ordning → Egen ordning** låter dig flytta dem med pilar eller dra dem i normalvyn. **Kompakt vy** behåller ordningen utan redigeringsknappar.
3. Exportera nästa tömningar till en `.ics`-kalender. **Inbäddad vy** visar endast tömningsuppgifter. Installation, feedback och påminnelser beror på serverns inställningar och webbläsarstöd.

Det är frivilligt att spara inloggningsuppgifter. Webbläsarens datablob är inte säker kryptering; spara inte på delade enheter och håll inbäddningslänkar med inloggningsuppgifter hemliga. Påminnelser bygger på den senaste lyckade hämtningen i webbläsaren. Gamla sparade uppgifter markeras som inaktuella.

Mer: [fullständig guide (finska)](README.md), [installation och inställningar (finska)](TECHNICAL.md), [API (finska)](API.md), [ändringar (engelska)](CHANGELOG.md), [tester (engelska)](https://github.com/janilahti/renyyt/blob/main/TESTING.md).
