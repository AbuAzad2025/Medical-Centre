import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
from bs4 import BeautifulSoup

s = requests.Session()
BASE = "http://127.0.0.1:5001"

# Login
r = s.get(f"{BASE}/auth/login")
soup = BeautifulSoup(r.content, 'html.parser')
csrf = soup.find('input', {'name': 'csrf_token'})

if csrf:
    r = s.post(f"{BASE}/auth/login", data={
        'username': 'admin',
        'password': 'Admin@12345',
        'csrf_token': csrf.get('value')
    })

# Get dashboard
r = s.get(f"{BASE}/super-admin/dashboard")
soup = BeautifulSoup(r.content, 'html.parser')

# Save to file to see
with open('dashboard_real.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())

print("تم حفظ الصفحة في dashboard_real.html")

# Analyze
h1 = soup.find('h1')
print(f"\nالعنوان الرئيسي: {h1.text.strip() if h1 else 'لا يوجد'}")

# Find all buttons
buttons = soup.find_all('a', class_='btn')
print(f"\nعدد الأزرار: {len(buttons)}")
print("\nالأزرار الموجودة:")
for i, btn in enumerate(buttons[:15], 1):
    text = btn.get_text(strip=True)
    href = btn.get('href', '#')
    print(f"  {i}. {text[:50]} -> {href}")

# Find cards
cards = soup.find_all('div', class_='card')
print(f"\nعدد البطاقات: {len(cards)}")

# Check for stats
stats_divs = soup.find_all('h3')
print(f"\nعدد الإحصائيات: {len(stats_divs)}")

