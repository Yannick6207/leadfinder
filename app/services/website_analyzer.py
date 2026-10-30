import ipaddress
import re
import socket
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import current_app


class UnsafeUrlError(ValueError): pass


def _validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrlError("Alleen publieke HTTP(S)-websites zijn toegestaan.")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeUrlError("Domeinnaam kan niet worden gevonden.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrlError("Lokale of private adressen worden niet geanalyseerd.")
    return parsed


def analyze_website(url, timeout=None):
    timeout = timeout or current_app.config.get("WEBSITE_TIMEOUT", 5)
    _validate_public_url(url)
    headers = {"User-Agent": "YN-Webdesign-LeadFinder/1.0 (+local website quality check)"}
    started = time.perf_counter()
    response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=False, stream=True)
    redirects = 0
    while response.is_redirect and redirects < 3:
        next_url = urljoin(response.url, response.headers.get("Location", "")); _validate_public_url(next_url)
        response.close(); response = requests.get(next_url, timeout=timeout, headers=headers, allow_redirects=False, stream=True); redirects += 1
    response.raise_for_status()
    if "text/html" not in response.headers.get("Content-Type", "text/html"):
        raise ValueError("De URL levert geen HTML-pagina.")
    content = response.raw.read(1_500_001, decode_content=True)
    response.close()
    if len(content) > 1_500_000: raise ValueError("De HTML-pagina is te groot om veilig te analyseren.")
    elapsed = round(time.perf_counter() - started, 2)
    soup = BeautifulSoup(content, "html.parser"); html = str(soup).lower(); text = soup.get_text(" ", strip=True).lower()
    viewport = bool(soup.find("meta", attrs={"name": re.compile("viewport", re.I)}))
    title = bool(soup.title and soup.title.get_text(strip=True))
    meta_desc = bool(soup.find("meta", attrs={"name": re.compile("description", re.I), "content": True}))
    contact_form = bool(soup.find("form") and ("contact" in html or "bericht" in text))
    social = any(domain in html for domain in ("instagram.com", "facebook.com", "linkedin.com"))
    contact = bool(re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I) or re.search(r"(?:\+31|0)[\s()-]*\d", text))
    outdated = [signal for signal in ("<font", "<frameset", "flash", "jquery-1.") if signal in html]
    years = [int(y) for y in re.findall(r"(?:©|copyright)[^0-9]{0,12}(20\d{2})", text, re.I)]
    copyright_year = max(years) if years else None
    score = 25 + (10 if response.url.startswith("https://") else 0) + (15 if viewport else 0) + (10 if title else 0) + (10 if meta_desc else 0) + (10 if contact else 0) + (8 if contact_form else 0) + (5 if social else 0)
    if elapsed <= 1.5: score += 7
    elif elapsed > 4: score -= 10
    score -= len(outdated) * 8
    if copyright_year and copyright_year < datetime.now().year - 3: score -= 8
    score = max(0, min(100, score))
    recommendations = []
    for ok, message in [(response.url.startswith("https://"), "Schakel HTTPS in."), (viewport, "Voeg een viewport-meta-tag toe."), (title, "Voeg een duidelijke paginatitel toe."), (meta_desc, "Voeg een meta description toe."), (contact, "Maak contactgegevens zichtbaar."), (contact_form, "Voeg een contactformulier toe."), (social, "Koppel socialmedia-profielen.")]:
        if not ok: recommendations.append(message)
    if outdated: recommendations.append("Vervang verouderde HTML-technieken: " + ", ".join(outdated))
    return {"reachable": True, "https": response.url.startswith("https://"), "response_time": elapsed, "mobile_friendly": viewport, "viewport_present": viewport, "title_present": title, "meta_description_present": meta_desc, "contact_details_present": contact, "contact_form_present": contact_form, "social_links_present": social, "broken_links_count": 0, "detected_copyright_year": copyright_year, "outdated_html_signals": ", ".join(outdated), "score": score, "recommendations": "\n".join(recommendations) or "Geen directe basisproblemen gevonden."}


def website_status(score):
    if score is None: return "Nog niet gecontroleerd"
    if score < 50: return "Slechte website"
    if score < 75: return "Redelijke website"
    return "Goede website"
