import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import requests
from bs4 import BeautifulSoup
import re
import time
from models import db, CycloneImpact
from app import app
from sqlalchemy import and_
import json

URL = "https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin"
GEOCODE_URL = "https://nominatim.openstreetmap.org/search"

def geocode_area(area_name):
    params = {
        'q': area_name + ', Philippines',
        'format': 'json',
        'limit': 1
    }
    resp = requests.get(GEOCODE_URL, params=params, headers={'User-Agent': 'BahaWatchPH/1.0'})
    data = resp.json()
    if data:
        return float(data[0]['lat']), float(data[0]['lon'])
    return None, None

def extract_affected_areas_from_text(text):
    # Find all "Affected Areas" blocks
    affected_areas = set()
    pattern = re.compile(r'Affected Areas\s*Luzon\s*(.*?)\s*Visayas\s*(.*?)\s*Mindanao\s*(.*?)\s*Meteorological Condition', re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    if match:
        for group in match.groups():
            # Split by commas, and also extract items in parentheses
            for part in group.split(','):
                part = part.strip()
                # Extract items in parentheses
                if '(' in part and ')' in part:
                    before_paren = part[:part.index('(')].strip()
                    if before_paren:
                        affected_areas.add(before_paren)
                    inside = part[part.index('(')+1:part.index(')')]
                    for item in inside.split(','):
                        item = item.strip()
                        if item:
                            affected_areas.add(item)
                else:
                    if part and part.lower() not in ['-', '']:
                        affected_areas.add(part)
    return list(affected_areas)

def scrape_pagasa_bulletin():
    resp = requests.get(URL)
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(separator='\n')

    # Storm name
    storm_name = None
    for tag in soup.find_all(["h3", "h4"]):
        if re.search(r"(Tropical Storm|Typhoon)", tag.get_text(), re.I):
            storm_name = tag.get_text(strip=True)
            break

    # Bulletin number, issue time, summary, hazards
    bulletin = soup.find(string=lambda s: s and "Tropical Cyclone Bulletin" in s)
    bulletin_number = bulletin.strip() if bulletin else None
    issue_time = None
    for tag in soup.find_all(["h5", "div"]):
        if tag.get_text(strip=True).startswith("Issued at"):
            issue_time = tag.get_text(strip=True)
            break
    summary = None
    for tag in soup.find_all("h5"):
        if "maintained its strength" in tag.get_text().lower():
            summary = tag.get_text(strip=True)
            break
    # Hazards: only those after the summary
    hazards = []
    found_summary = False
    for el in soup.find_all(['h5', 'ul']):
        if summary and el.get_text(strip=True) == summary:
            found_summary = True
        elif found_summary and el.name == 'ul' and found_summary:
            for li in el.find_all('li'):
                hazards.append(li.get_text(strip=True))
            break
    # Save bulletin info to JSON
    bulletin_data = {
        'bulletin': bulletin_number,
        'storm_name': storm_name,
        'issue_time': issue_time,
        'summary': summary,
        'hazards': hazards
    }
    with open(os.path.join(os.path.dirname(__file__), 'cyclone_bulletin.json'), 'w', encoding='utf-8') as f:
        json.dump(bulletin_data, f, ensure_ascii=False, indent=2)

    # Extract affected areas from text
    affected_areas = extract_affected_areas_from_text(text)
    print(f"[DEBUG] Parsed affected areas: {affected_areas}")
    inserted, skipped, failed = 0, 0, 0
    with app.app_context():
        for area in affected_areas:
            lat, lng = geocode_area(area)
            if lat and lng:
                exists = CycloneImpact.query.filter(and_(CycloneImpact.area == area, CycloneImpact.description == f'Affected by {storm_name}')).first()
                if not exists:
                    impact = CycloneImpact(
                        area=area,
                        lat=lat,
                        lng=lng,
                        status='Alert',
                        description=f'Affected by {storm_name}'
                    )
                    db.session.add(impact)
                    db.session.commit()
                    print(f'[DEBUG] Inserted: {area} ({lat}, {lng})')
                    inserted += 1
                else:
                    print(f'[DEBUG] Skipped duplicate: {area}')
                    skipped += 1
            else:
                print(f'[DEBUG] Geocoding failed: {area}')
                failed += 1
            time.sleep(1)
    print(f"[DEBUG] Summary: Inserted={inserted}, Skipped={skipped}, GeocodingFailed={failed}")

if __name__ == "__main__":
    scrape_pagasa_bulletin() 