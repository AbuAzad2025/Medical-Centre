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

print("="*80)
print("تصفح بصري للوحة Super Admin")
print("="*80)

# 1. Check navbar
nav = soup.find('nav', class_='nav')
if nav:
    nav_links = nav.find_all('a', class_='nav-link')
    print(f"\n📌 الـ Navbar يحتوي على {len(nav_links)} رابط:")
    for i, link in enumerate(nav_links, 1):
        text = link.get_text(strip=True)
        icon = link.find('i')
        icon_class = icon.get('class')[1] if icon and len(icon.get('class', [])) > 1 else 'no-icon'
        print(f"   {i}. {text} ({icon_class})")
else:
    print("\n❌ الـ Navbar غير موجود!")

# 2. Check main content
print(f"\n📄 المحتوى الرئيسي:")
h1 = soup.find('h1')
if h1:
    print(f"   العنوان: {h1.get_text(strip=True)}")

# 3. Check statistics cards
stat_cards = soup.find_all('div', class_='card')
print(f"   عدد البطاقات: {len(stat_cards)}")

# 4. Check buttons section
print(f"\n🔘 الأزرار:")
buttons_section = soup.find(string=lambda text: text and 'الوظائف الرئيسية' in text)
if buttons_section:
    print("   ✓ قسم الوظائف الرئيسية موجود")
    parent = buttons_section.find_parent('div', class_='card')
    if parent:
        buttons = parent.find_all('a', class_='btn')
        print(f"   عدد الأزرار: {len(buttons)}")
        for i, btn in enumerate(buttons, 1):
            text = btn.find('strong')
            if text:
                print(f"   {i}. {text.get_text(strip=True)}")
else:
    print("   ❌ قسم الوظائف غير موجود!")

# 5. Check statistics
print(f"\n📊 الإحصائيات:")
stats = soup.find_all('h3')
print(f"   عدد الإحصائيات: {len(stats)}")
for i, stat in enumerate(stats[:5], 1):
    print(f"   {i}. {stat.get_text(strip=True)}")

print("\n" + "="*80)

