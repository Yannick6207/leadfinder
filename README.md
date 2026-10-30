# YN Webdesign Lead Finder

Een lokale Flask-webapp om interessante bedrijven in Gelderland te vinden, beoordelen en opvolgen. De MVP werkt direct met fictieve data en een verwisselbare mock-provider; er wordt geen ongeoorloofde scraping gebruikt.

## Wat werkt

- Dashboard met actuele databasecijfers en grafieken per status, branche en plaats.
- Lead Finder met providerarchitectuur, voortgangsindicator en deduplicatie.
- Filters, vrije zoekfunctie, sortering en favorieten.
- Verklaarbare leadscore van 0–100 met centraal instelbare regels.
- Veilige websiteanalyse met time-outs, redirectsbeperking, inhoudslimiet en blokkade van private/lokale IP-adressen.
- Salespipeline, contactmomenten, notities en interne opmerkingen.
- Lead-detailpagina, websitekwaliteit, acties en demo-promptgenerator.
- CSV-import en Excel-vriendelijke CSV-export.
- 18 fictieve Gelderse bedrijven verdeeld over meerdere branches en websitekwaliteiten.
- Responsive SaaS-interface voor desktop, tablet en telefoon.

## Projectstructuur

```text
leadfinder/
├── app/
│   ├── routes/             # Pagina- en JSON-routes
│   ├── services/           # Provider, scoring, analyse en seeddata
│   ├── static/css/         # Interface-styling
│   ├── static/js/          # Interacties en grafieken
│   ├── templates/          # Jinja-schermen
│   ├── models.py           # SQLAlchemy-modellen
│   └── extensions.py
├── instance/               # Lokale SQLite-database
├── tests/
├── config.py
├── requirements.txt
└── run.py
```

## Installatie op Windows

1. Installeer Python 3.11 of nieuwer via [python.org](https://www.python.org/downloads/). Vink tijdens installatie **Add Python to PATH** aan.
2. Open PowerShell in deze map.
3. Maak en activeer een virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

4. Installeer dependencies:

```powershell
python -m pip install -r requirements.txt
```

5. Maak de lokale configuratie:

```powershell
Copy-Item .env.example .env
```

Vervang in `.env` minstens `SECRET_KEY` door een lange willekeurige waarde. API-sleutels horen alleen in `.env`, nooit in HTML of JavaScript.

6. Maak de database en voeg testdata toe:

```powershell
flask --app run.py init-db
flask --app run.py seed
```

Resetten naar de meegeleverde testdata kan met:

```powershell
flask --app run.py seed --reset
```

7. Start de applicatie:

```powershell
python run.py
```

Open daarna `http://127.0.0.1:5000`.

## Tests uitvoeren

```powershell
pytest -q
```

De tests gebruiken een tijdelijke in-memory SQLite-database en wijzigen de normale database niet.

## Echte bedrijven ophalen via Google Places

De meegeleverde `GooglePlacesProvider` gebruikt de officiële Places API (New), Text Search en Place Details. Activeer in Google Cloud **Places API (New)**, koppel billing, beperk de sleutel tot deze API en zet vervolgens in `.env`:

```dotenv
BUSINESS_PROVIDER=google_places
GOOGLE_PLACES_API_KEY=plaats-hier-de-server-side-key
PLACES_TIMEOUT=10
```

Herstart de Flask-app na een wijziging in `.env`. Zoek daarna via **Lead Finder** op een plaats en branche. De provider vraagt alleen naam, categorie, adrescomponenten, telefoon, website, rating en reviewaantal op. Het beperkte field mask voorkomt onnodige velden en kosten.

Google Places levert geen zakelijke e-mailadressen, Instagram- of Facebookprofielen. Deze velden blijven bij Google-resultaten leeg. Verrijk ze alleen via bronnen en voorwaarden die dit expliciet toestaan. Pas providerquota, attribution, opslagregels en Google Maps Platform-voorwaarden toe zoals Google voorschrijft.

Voor een andere databron kan nog steeds een extra class worden toegevoegd die `BusinessProvider` implementeert. Voeg de provider daarna toe aan `get_provider()`.

## Websiteanalyse en veiligheid

De analyzer doet alleen een beperkte basiscontrole van de opgegeven homepage. Hij valideert DNS/IP-adressen tegen SSRF, accepteert alleen HTTP(S), volgt maximaal drie gecontroleerde redirects, leest maximaal 1,5 MB HTML en gebruikt een korte timeout. Broken-linkcontrole staat in de MVP op nul om websites niet onnodig te belasten; voeg dit later alleen toe met rate limits, robots/voorwaarden en een kleine gecontroleerde linkset.

## Productieplaatsing

Zet `debug=False`, gebruik een sterke `SECRET_KEY`, draai achter een productie-WSGI-server en reverse proxy, maak databaseback-ups en beperk toegang tot deze CRM-app. Voor grotere datasets kan `DATABASE_URL` later naar PostgreSQL wijzen; de models en queries blijven via SQLAlchemy werken.
