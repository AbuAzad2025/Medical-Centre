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

print(f"Status: {r.status_code}")
print(f"Content length: {len(r.content)}")

# Check what's in the page
soup = BeautifulSoup(r.content, 'html.parser')

# Find the main content
main_content = soup.find('div', class_='container-fluid')
if main_content:
    # Find all rows
    rows = main_content.find_all('div', class_='row')
    print(f"\nعدد الصفوف: {len(rows)}")
    
    # Check for buttons section
    quick_actions = soup.find(string=lambda text: text and 'الوظائف الرئيسية' in text)
    print(f"\nقسم الوظائف موجود: {quick_actions is not None}")
    
    # Find all buttons
    all_buttons = soup.find_all('a', class_='btn')
    print(f"عدد الأزرار الكلي: {len(all_buttons)}")
    
    # Find specific section
    tasks_section = soup.find('i', class_='fa-tasks')
    print(f"أيقونة المهام موجودة: {tasks_section is not None}")
    
    # Check for the new buttons
    user_mgmt = soup.find(string=lambda text: text and 'إدارة المستخدمين' in text)
    print(f"زر إدارة المستخدمين موجود: {user_mgmt is not None}")

