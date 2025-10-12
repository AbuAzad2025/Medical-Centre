# خريطة العلاقات في النظام الصحي
# تم إنشاؤها لضمان عدم وجود تعارضات في العلاقات

"""
خريطة العلاقات الأساسية:

1. User (المستخدمين)
   - department_obj: Department (القسم)
   - head_department: Department (رئيس القسم)
   - doctor_visits: Visit (زيارات الطبيب)
   - patient_visits: PatientVisit (زيارات المريض)
   - doctor_appointments: Appointment (مواعيد الطبيب)
   - created_appointments: Appointment (المواعيد المنشأة)
   - created_invoices: Invoice (الفواتير المنشأة)
   - created_payments: Payment (المدفوعات المنشأة)
   - created_financial_payments: FinancialPayment (المدفوعات المالية المنشأة)
   - updated_invoices: Invoice (الفواتير المحدثة)
   - force_payment_approvals: Invoice (موافقات الدفع القسري)

2. Patient (المرضى)
   - visits: Visit (الزيارات)
   - appointments: Appointment (المواعيد)
   - medical_records: MedicalRecord (السجلات الطبية)
   - lab_results: LabResult (نتائج المختبر)
   - radiology_results: RadiologyResult (نتائج الأشعة)
   - medical_reports: MedicalReport (التقارير الطبية)
   - prescriptions: Prescription (الوصفات)
   - lab_requests: LabRequest (طلبات المختبر)
   - radiology_requests: RadiologyRequest (طلبات الأشعة)
   - invoices: Invoice (الفواتير)
   - payments: Payment (المدفوعات)
   - patient_visits: PatientVisit (زيارات المريض)
   - medical_history_records: PatientMedicalHistory (التاريخ الطبي)
   - allergy_records: PatientAllergy (سجلات الحساسية)
   - medication_records: PatientMedication (سجلات الأدوية)
   - financial_payments: FinancialPayment (المدفوعات المالية)

3. Visit (الزيارات)
   - patient: Patient (المريض)
   - doctor: User (الطبيب)
   - department: Department (القسم)
   - patient_visits: PatientVisit (زيارات المريض)
   - payments: Payment (المدفوعات)
   - medical_records: MedicalRecord (السجلات الطبية)
   - treatments: Treatment (العلاجات)
   - lab_requests: LabRequest (طلبات المختبر)
   - radiology_requests: RadiologyRequest (طلبات الأشعة)
   - invoices: Invoice (الفواتير)
   - financial_payments: FinancialPayment (المدفوعات المالية)

4. Department (الأقسام)
   - head_doctor: User (رئيس القسم)
   - users: User (المستخدمين)
   - staff: User (الموظفين)
   - appointments: Appointment (المواعيد)
   - visits: Visit (الزيارات)
   - patient_visits: PatientVisit (زيارات المريض)
   - invoice_services: InvoiceService (خدمات الفواتير)

5. Appointment (المواعيد)
   - patient: Patient (المريض)
   - doctor: User (الطبيب)
   - department: Department (القسم)
   - creator: User (المنشئ)
   - financial_payments: FinancialPayment (المدفوعات المالية)

6. Payment (المدفوعات)
   - patient: Patient (المريض)
   - visit: Visit (الزيارة)
   - invoice: Invoice (الفاتورة)
   - creator: User (المنشئ)

7. FinancialPayment (المدفوعات المالية)
   - patient: Patient (المريض)
   - visit: Visit (الزيارة)
   - appointment: Appointment (الموعد)
   - creator: User (المنشئ)

8. Invoice (الفواتير)
   - patient: Patient (المريض)
   - visit: Visit (الزيارة)
   - creator: User (المنشئ)
   - updater: User (المحدث)
   - force_approver: User (موافق الدفع القسري)
   - payments: Payment (المدفوعات)
   - services: InvoiceService (الخدمات)

9. PatientVisit (زيارات المريض)
   - patient: Patient (المريض)
   - visit: Visit (الزيارة)
   - doctor: User (الطبيب)
   - department: Department (القسم)

10. PatientMedicalHistory (التاريخ الطبي)
    - patient: Patient (المريض)

11. PatientAllergy (الحساسيات)
    - patient: Patient (المريض)

12. PatientMedication (الأدوية)
    - patient: Patient (المريض)
"""

# قائمة العلاقات المطلوبة لكل نموذج
REQUIRED_RELATIONSHIPS = {
    'User': [
        'department_obj', 'head_department', 'doctor_visits', 'patient_visits',
        'doctor_appointments', 'created_appointments', 'created_invoices',
        'created_payments', 'created_financial_payments', 'updated_invoices',
        'force_payment_approvals'
    ],
    'Patient': [
        'visits', 'appointments', 'medical_records', 'lab_results',
        'radiology_results', 'medical_reports', 'prescriptions',
        'lab_requests', 'radiology_requests', 'invoices', 'payments',
        'patient_visits', 'medical_history_records', 'allergy_records',
        'medication_records', 'financial_payments'
    ],
    'Visit': [
        'patient', 'doctor', 'department', 'patient_visits', 'payments',
        'medical_records', 'treatments', 'lab_requests', 'radiology_requests',
        'invoices', 'financial_payments'
    ],
    'Department': [
        'head_doctor', 'users', 'staff', 'appointments', 'visits',
        'patient_visits', 'invoice_services'
    ],
    'Appointment': [
        'patient', 'doctor', 'department', 'creator', 'financial_payments'
    ],
    'Payment': [
        'patient', 'visit', 'invoice', 'creator'
    ],
    'FinancialPayment': [
        'patient', 'visit', 'appointment', 'creator'
    ],
    'Invoice': [
        'patient', 'visit', 'creator', 'updater', 'force_approver',
        'payments', 'services'
    ],
    'PatientVisit': [
        'patient', 'visit', 'doctor', 'department'
    ],
    'PatientMedicalHistory': [
        'patient'
    ],
    'PatientAllergy': [
        'patient'
    ],
    'PatientMedication': [
        'patient'
    ]
}
