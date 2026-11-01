# AZAD Medical Centre Platform - User Manual

## Getting Started

### Login
1. Open your browser and navigate to `http://localhost:8000`
2. Enter your username and password
3. Click "تسجيل الدخول" (Login)

### Default Accounts
| Role | Username | Password |
|------|----------|----------|
| Super Admin | superadmin | (generated on first run) |
| Admin | admin | Password@123 |
| Manager | manager | Password@123 |
| Reception | reception | Password@123 |
| Doctor | doctor | Password@123 |
| Pharmacist | pharmacist | Password@123 |
| Lab Tech | lab | Password@123 |
| Nurse | nurse | Password@123 |
| Emergency | emergency | Password@123 |
| Accountant | accountant | Password@123 |
| Radiology | radiology | Password@123 |

### Navigation
- Use the **sidebar** on the right for navigation
- Click the **language switcher** (🌐) to toggle between Arabic and English
- Click the **theme toggle** (🌙) for dark mode
- Use **search bar** (top center) to search patients, appointments, prescriptions

### Patient Management
1. Go to **Reception → Patients**
2. Click "إضافة مريض" (Add Patient)
3. Fill in: First Name, Last Name, National ID, Phone, Birth Date, Gender, Address
4. Click "حفظ" (Save)

### Visits
1. Go to **Reception → Create Visit**
2. Select patient, doctor, department
3. Click "إنشاء زيارة" (Create Visit)
4. Visit appears in queue

### Prescriptions
1. Go to **Doctor → Prescriptions**
2. Select patient and visit
3. Add medications with dosage and quantity
4. Click "حفظ" (Save)

### Lab Requests
1. Go to **Doctor → Lab** or **Lab → Worklist**
2. Create lab request
3. Enter results
4. Validate results

### Radiology
1. Go to **Doctor → Radiology** or **Radiology → Worklist**
2. Create radiology request
3. Upload images
4. Enter report

### Emergency
1. Go to **Emergency → Dashboard**
2. Create emergency case
3. Triage patient
4. Document treatment

### Pharmacy
1. Go to **Pharmacy → POS** for direct sales
2. Go to **Medication → Prescriptions** for dispensing
3. Manage inventory in **Medication → List**

### Billing
1. Go to **Finance → Dashboard**
2. Create invoice from visit
3. Process payment
4. Print receipt

### Reports
1. Go to **Manager → Reports**
2. Select report type
3. Export to PDF/Excel

### Admin Functions
1. Go to **Super Admin → Dashboard**
2. Manage users, departments, services, roles
3. Configure system settings
4. View audit logs

### Owner Console
1. Go to **Owner → Dashboard**
2. Manage tenants, packages, subscriptions
3. View platform analytics
4. Configure branding

### Language Switching
- Click the **globe icon** (🌐) in the navbar
- Select **🇸🇦 العربية** or **🇬🇧 English**
- Interface switches immediately

### Dark Mode
- Click the **moon icon** (🌙) in the navbar
- Toggle between light and dark themes

### Sidebar Navigation
- **Left/Right toggle**: Click the arrow button (top-right of sidebar)
- **Collapse**: Click the collapse button to minimize sidebar
- **Mobile**: Swipe or tap the menu button

### Backup
- Go to **Super Admin → Backup**
- Click "Create Backup" for manual backup
- Automated backups run via Celery (if configured)