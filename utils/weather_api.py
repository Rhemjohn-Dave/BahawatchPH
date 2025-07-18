import requests
from bs4 import BeautifulSoup

DASHBOARD_URL = 'https://philsensors.asti.dost.gov.ph/site/dashboard'

# Note: This is a basic scraper. The dashboard may change structure or require authentication in the future.
def get_philsensors_rainfall():
    response = requests.get(DASHBOARD_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    stations = []
    # Example: Find all station rows (update selector as needed)
    for row in soup.select('tr'):
        cols = row.find_all('td')
        if len(cols) >= 4:
            station = cols[0].get_text(strip=True)
            location = cols[1].get_text(strip=True)
            rainfall = cols[2].get_text(strip=True)
            # lat/lng may not be present; set to None or parse if available
            stations.append({
                'station': station,
                'location': location,
                'lat': None,
                'lng': None,
                'rainfall': rainfall
            })
    return stations

if __name__ == '__main__':
    data = get_philsensors_rainfall()
    for s in data[:10]:  # Print first 10 for preview
        print(s) 