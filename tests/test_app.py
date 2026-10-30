import pytest
from app import create_app
from app.extensions import db
from app.models import Lead
from app.services.scoring import calculate_lead_score
from app.services.seed import seed_database
from app.services.providers import GooglePlacesProvider, ProviderError
from config import TestConfig


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all(); seed_database()
        yield app
        db.session.remove(); db.drop_all()


@pytest.fixture()
def client(app): return app.test_client()


def test_dashboard_and_main_screens(client):
    for path in ("/", "/leads", "/finder", "/pipeline", "/settings"):
        response = client.get(path)
        assert response.status_code == 200
    assert b"YN Webdesign" in client.get("/").data


def test_seed_contains_varied_gelderland_leads(app):
    with app.app_context():
        assert Lead.query.count() >= 15
        assert Lead.query.filter_by(province="Gelderland").count() == Lead.query.count()
        assert Lead.query.filter_by(website_status="Geen website").count() > 0
        assert Lead.query.filter_by(website_status="Goede website").count() > 0


def test_lead_score_is_capped(app):
    with app.app_context():
        lead = Lead(company_name="Test", website_status="Geen website", phone="061", email="a@b.nl", instagram="x", google_rating=4.8, google_review_count=99)
        score, reasons = calculate_lead_score(lead)
        assert score == 100
        assert len(reasons) >= 6


def test_mock_search_deduplicates(client, app):
    payload = {"city": "Arnhem", "category": "Kapper", "limit": 3}
    first = client.post("/api/search", json=payload).get_json(); second = client.post("/api/search", json=payload).get_json()
    assert len(first["created"]) == 3
    assert len(second["created"]) == 0
    assert second["duplicates"] == 3


def test_update_status_and_favorite(client, app):
    with app.app_context():
        lead = Lead.query.first(); lead_id = lead.id; before = lead.favorite
    assert client.post(f"/api/leads/{lead_id}/favorite").get_json()["favorite"] is (not before)
    assert client.patch(f"/api/leads/{lead_id}/status", json={"status": "Gebeld"}).get_json()["status"] == "Gebeld"


def test_csv_export(client):
    response = client.get("/export.csv")
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/csv")
    assert b"company_name" in response.data


class FakeGoogleResponse:
    status_code = 200

    def json(self):
        return {"places": [{
            "id": "ChIJ-test-place",
            "displayName": {"text": "Echte Kapper Arnhem"},
            "primaryTypeDisplayName": {"text": "Kapper"},
            "formattedAddress": "Markt 1, 6811 CG Arnhem, Nederland",
            "addressComponents": [
                {"longText": "Arnhem", "types": ["locality"]},
                {"longText": "Gelderland", "types": ["administrative_area_level_1"]},
            ],
            "internationalPhoneNumber": "+31 26 123 4567",
            "websiteUri": "https://voorbeeld.nl",
            "rating": 4.6,
            "userRatingCount": 73,
        }]}


class FakeGoogleSession:
    def __init__(self): self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeGoogleResponse()


def test_google_provider_normalises_official_response():
    session = FakeGoogleSession()
    provider = GooglePlacesProvider("test-key", session=session)
    results = provider.search_businesses("Arnhem", "Kapper", 1)
    assert results[0]["company_name"] == "Echte Kapper Arnhem"
    assert results[0]["city"] == "Arnhem"
    assert results[0]["google_review_count"] == 73
    method, _, kwargs = session.calls[0]
    assert method == "POST"
    assert kwargs["headers"]["X-Goog-Api-Key"] == "test-key"
    assert "places.websiteUri" in kwargs["headers"]["X-Goog-FieldMask"]
    assert kwargs["json"]["textQuery"] == "Kapper in Arnhem, Gelderland, Nederland"


def test_google_provider_requires_key():
    with pytest.raises(ProviderError):
        GooglePlacesProvider("")
