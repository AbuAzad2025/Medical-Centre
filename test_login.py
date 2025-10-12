import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
from bs4 import BeautifulSoup

s = requests.Session()
BASE = "http://127.0.0.1:5001"

# Get login page
r = s.get(f"{BASE}/auth/login")
soup = BeautifulSoup(r.content, 'html.parser')
csrf = soup.find('input', {'name': 'csrf_token'})

if csrf:
    # Login
    r = s.post(f"{BASE}/auth/login", data={
        'username': 'admin',
        'password': 'Admin@12345',
        'csrf_token': csrf.get('value')
    })
    
    print(f"Login Status: {r.status_code}")
    print(f"Final URL: {r.url}")
    
    # Try to access dashboard
    r = s.get(f"{BASE}/super-admin/dashboard")
    print(f"\nDashboard Status: {r.status_code}")
    print(f"Dashboard URL: {r.url}")
    
    if r.status_code == 200:
        soup = BeautifulSoup(r.content, 'html.parser')
        h1 = soup.find('h1')
        print(f"Page Title: {h1.text.strip() if h1 else 'N/A'}")
        
        # Count buttons
        buttons = soup.find_all('a', class_='btn')
        print(f"Number of buttons: {len(buttons)}")
        
        # Find main sections
        cards = soup.find_all('div', class_='card')
        print(f"Number of cards: {len(cards)}")

