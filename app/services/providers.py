from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

import requests
from flask import current_app

GOOGLE_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
GOOGLE_SEARCH_FIELDS = ",".join(["places.id", "places.displayName", "places.formattedAddress", "places.addressComponents", "places.primaryTypeDisplayName", "places.internationalPhoneNumber", "places.websiteUri", "places.rating", "places.userRatingCount", "nextPageToken"])
GOOGLE_DETAILS_FIELDS = ",".join(["id", "displayName", "formattedAddress", "addressComponents", "primaryTypeDisplayName", "internationalPhoneNumber", "websiteUri", "rating", "userRatingCount"])


class ProviderError(RuntimeError):
    """Veilige, gebruikersgerichte fout van een externe bedrijfsprovider."""


@dataclass
class BusinessResult:
    external_id: str
    company_name: str
    category: str
    address: str
    city: str
    municipality: str
    province: str = "Gelderland"
    phone: str = ""
    email: str = ""
    website: str = ""
    instagram: str = ""
    facebook: str = ""
    google_rating: float | None = None
    google_review_count: int = 0


class BusinessProvider(ABC):
    @abstractmethod
    def search_businesses(self, city, category, limit=10): ...

    @abstractmethod
    def get_business_details(self, external_id): ...


class MockBusinessProvider(BusinessProvider):
    CATEGORIES = ["Kapper", "Schilder", "Aannemer", "Garage", "Installateur", "Schoonheidssalon", "Restaurant", "Fysiotherapeut", "Elektricien", "Barbershop"]

    def search_businesses(self, city, category, limit=10):
        city = city or "Arnhem"
        category = category or "Lokale ondernemer"
        rows = []
        for i in range(min(max(int(limit), 1), 50)):
            has_site = i % 3 != 0
            rows.append(BusinessResult(
                external_id=f"mock-{city.lower()}-{category.lower()}-{i}",
                company_name=f"{category} {['De Brug','Veluwe','De Markt','Rijnzicht','Gelderse Hof'][i % 5]} {i + 1}",
                category=category,
                address=f"{['Markt','Dorpsstraat','Stationsweg','Rijnkade'][i % 4]} {12+i}",
                city=city,
                municipality=city,
                phone=f"06-{12003000+i:08d}",
                email=f"contact{i+1}@voorbeeldbedrijf.nl" if i % 4 else "",
                website=f"https://voorbeeldbedrijf{i+1}.nl" if has_site else "",
                instagram=f"https://instagram.com/voorbeeldbedrijf{i+1}" if i % 2 == 0 else "",
                facebook=f"https://facebook.com/voorbeeldbedrijf{i+1}" if i % 3 == 0 else "",
                google_rating=round(3.7 + (i % 6) * .2, 1),
                google_review_count=7 + i * 9,
            ))
        return [asdict(row) for row in rows]

    def get_business_details(self, external_id):
        return {"external_id": external_id}


class GooglePlacesProvider(BusinessProvider):
    """Officiële Google Places API (New)-provider, uitsluitend server-side."""

    def __init__(self, api_key, timeout=10, session=None):
        if not api_key:
            raise ProviderError("GOOGLE_PLACES_API_KEY ontbreekt in het .env-bestand.")
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def search_headers(self):
        return {"Content-Type": "application/json", "X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": GOOGLE_SEARCH_FIELDS}

    def _request(self, method, url, **kwargs):
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.Timeout as exc:
            raise ProviderError("Google Places reageerde niet binnen de ingestelde tijd.") from exc
        except requests.RequestException as exc:
            raise ProviderError("Google Places kon niet worden bereikt.") from exc
        if response.status_code >= 400:
            try:
                message = response.json().get("error", {}).get("message", "")
            except ValueError:
                message = ""
            raise ProviderError(f"Google Places-fout: {message[:180] or f'HTTP {response.status_code}'}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("Google Places gaf een ongeldige response terug.") from exc

    @staticmethod
    def _component(place, wanted_types):
        for component in place.get("addressComponents", []):
            if wanted_types.intersection(component.get("types", [])):
                return component.get("longText", "")
        return ""

    def _normalise(self, place, fallback_city="", fallback_category=""):
        display_name = place.get("displayName") or {}
        category_name = place.get("primaryTypeDisplayName") or {}
        city = self._component(place, {"locality", "postal_town"}) or fallback_city
        municipality = self._component(place, {"administrative_area_level_2"}) or city
        province = self._component(place, {"administrative_area_level_1"}) or "Gelderland"
        return asdict(BusinessResult(
            external_id=place.get("id", ""),
            company_name=display_name.get("text", "Onbekend bedrijf"),
            category=category_name.get("text", "") or fallback_category,
            address=place.get("formattedAddress", ""),
            city=city,
            municipality=municipality,
            province=province,
            phone=place.get("internationalPhoneNumber", ""),
            website=place.get("websiteUri", ""),
            google_rating=place.get("rating"),
            google_review_count=int(place.get("userRatingCount") or 0),
        ))

    def search_businesses(self, city, category, limit=10):
        city = (city or "Arnhem").strip()
        category = (category or "Lokale ondernemer").strip()
        limit = min(max(int(limit), 1), 50)
        results = []
        page_token = None
        while len(results) < limit:
            payload = {"textQuery": f"{category} in {city}, Gelderland, Nederland", "languageCode": "nl", "regionCode": "NL", "pageSize": min(20, limit - len(results))}
            if page_token:
                payload["pageToken"] = page_token
            data = self._request("POST", GOOGLE_SEARCH_URL, headers=self.search_headers, json=payload)
            results.extend(self._normalise(place, city, category) for place in data.get("places", []))
            page_token = data.get("nextPageToken")
            if not page_token or not data.get("places"):
                break
        return results[:limit]

    def get_business_details(self, external_id):
        if not external_id or "/" in external_id:
            raise ProviderError("Ongeldige Google Place ID.")
        headers = {"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": GOOGLE_DETAILS_FIELDS}
        place = self._request("GET", GOOGLE_DETAILS_URL.format(place_id=external_id), headers=headers)
        return self._normalise(place)


def get_provider():
    provider = current_app.config.get("BUSINESS_PROVIDER", "mock").strip().lower()
    if provider == "mock":
        return MockBusinessProvider()
    if provider == "google_places":
        return GooglePlacesProvider(current_app.config.get("GOOGLE_PLACES_API_KEY"), timeout=current_app.config.get("PLACES_TIMEOUT", 10))
    raise ProviderError(f"Provider '{provider}' is niet geconfigureerd.")
