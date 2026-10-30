from datetime import date, timedelta
from ..extensions import db
from ..models import Lead, WebsiteAnalysis
from .scoring import update_lead_score


SEED_ROWS = [
 ("Barbershop De Baard", "Barbershop", "Lochem", "Geen website", None, 4.7, 84),
 ("Kapsalon Linde", "Kapper", "Zutphen", "Slechte website", 38, 4.4, 51),
 ("Schilderwerken Veluwe", "Schilder", "Apeldoorn", "Geen website", None, 4.8, 39),
 ("Bouwbedrijf De IJssel", "Aannemer", "Doetinchem", "Redelijke website", 66, 4.2, 27),
 ("Garage Rijnzicht", "Garage", "Arnhem", "Slechte website", 42, 4.6, 116),
 ("Installatiebedrijf Oost", "Installateur", "Winterswijk", "Geen website", None, 4.5, 22),
 ("Studio Puur", "Schoonheidssalon", "Nijmegen", "Goede website", 88, 4.9, 143),
 ("Restaurant Het Stadshof", "Restaurant", "Tiel", "Redelijke website", 71, 4.3, 208),
 ("Fysio De Brink", "Fysiotherapeut", "Ede", "Goede website", 91, 4.7, 97),
 ("Elektro Van Dalen", "Elektricien", "Harderwijk", "Geen website", None, 4.6, 18),
 ("Kapper aan de Kade", "Kapper", "Arnhem", "Slechte website", 31, 4.1, 36),
 ("Aannemersbedrijf Berkel", "Aannemer", "Lochem", "Geen website", None, 4.8, 14),
 ("Garage De Achterhoek", "Garage", "Doetinchem", "Redelijke website", 62, 4.5, 72),
 ("Salon Roos", "Schoonheidssalon", "Zutphen", "Geen website", None, 4.9, 65),
 ("Bistro Markt Acht", "Restaurant", "Nijmegen", "Goede website", 83, 4.4, 312),
 ("Fysio Vitaal", "Fysiotherapeut", "Apeldoorn", "Slechte website", 46, 4.6, 45),
 ("Schilderscollectief Ede", "Schilder", "Ede", "Geen website", None, 4.2, 11),
 ("Installatietechniek Wientjes", "Installateur", "Winterswijk", "Goede website", 79, 4.7, 58),
]


def seed_database(reset=False):
    if reset:
        db.session.query(WebsiteAnalysis).delete(); db.session.query(Lead).delete(); db.session.commit()
    if Lead.query.count(): return Lead.query.count()
    for i, (name, category, city, status, webscore, rating, reviews) in enumerate(SEED_ROWS):
        has_website = status != "Geen website"
        lead = Lead(company_name=name, category=category, address=f"{['Dorpsstraat','Markt','Stationsweg','Kerkstraat'][i%4]} {8+i}", city=city, municipality=city, province="Gelderland", phone=f"0{6+i%4} - 12 34 {50+i:02d}", email=f"info@{name.lower().replace(' ', '').replace('é','e')}.nl" if i%3 else None, website=f"https://www.{name.lower().replace(' ', '').replace('é','e')}.nl" if has_website else None, instagram=f"https://instagram.com/{name.lower().replace(' ', '')}" if i%2==0 else None, facebook=f"https://facebook.com/{name.lower().replace(' ', '')}" if i%3==0 else None, google_rating=rating, google_review_count=reviews, website_status=status, website_score=webscore, pipeline_status=["Nieuw","Bellen","Gebeld","Afspraak","Offerte","Klant"][i%6], favorite=i in {0,4,9,13}, contact_person="", notes="", next_contact_date=date.today()+timedelta(days=i%7) if i%4==0 else None)
        update_lead_score(lead); db.session.add(lead); db.session.flush()
        if has_website:
            db.session.add(WebsiteAnalysis(lead_id=lead.id, reachable=True, https=i%3!=1, response_time=round(0.8+(i%5)*.7,1), mobile_friendly=webscore>=55, viewport_present=webscore>=55, title_present=True, meta_description_present=webscore>=65, contact_details_present=True, contact_form_present=webscore>=70, social_links_present=bool(lead.instagram or lead.facebook), detected_copyright_year=2026 if webscore>=70 else 2019, score=webscore, recommendations="Verbeter laadtijd en mobiele navigatie." if webscore<75 else "Geen directe basisproblemen gevonden."))
    db.session.commit(); return Lead.query.count()
