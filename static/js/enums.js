/**
 * enums.js — Auto-generated from app/shared/enums.py
 * 
 * المصدر الوحيد لكل الحالات والقيم في الواجهة الأمامية
 * Update by running: python -c "from app.shared.enums import generate_js; generate_js()"
 */

window.ENUMS = window.ENUMS || {};

// =============================================================================
// Status color map — Bootstrap badge classes
// =============================================================================
window.ENUMS.COLORS = {
  // Visit states
  OPEN: 'info',
  CHECKED_IN: 'primary',
  IN_PROGRESS: 'warning',
  COMPLETED: 'success',
  ARCHIVED: 'secondary',
  CANCELLED: 'danger',
  NO_SHOW: 'dark',
  // Appointment states
  SCHEDULED: 'primary',
  CONFIRMED: 'info',
  CHECKED_IN: 'primary',
  DONE: 'success',
  // Order states
  REQUESTED: 'primary',
  RECEIVED: 'info',
  ANALYZING: 'warning',
  REVIEWED: 'success',
  APPROVED: 'success',
  DRAFT: 'secondary',
  ORDERED: 'primary',
  SAMPLE_COLLECTED: 'info',
  RESULTS_ENTERED: 'success',
  DELIVERED: 'success',
  IMAGES_CAPTURED: 'info',
  REPORTED: 'success',
  // Billing states
  PENDING: 'warning',
  PAID: 'success',
  PARTIAL: 'warning',
  DEBT: 'danger',
  REFUNDED: 'danger',
  POSTED: 'info',
  ISSUED: 'primary',
  VOID: 'secondary',
  // Emergency states
  NEW: 'info',
  WAITING: 'warning',
  TRIAGE: 'warning',
  RESUSCITATION: 'danger',
  TREATMENT: 'primary',
  OBSERVATION: 'info',
  TRANSFERRED: 'secondary',
  // Queue states
  WAITING: 'warning',
  CALLED: 'info',
  SKIPPED: 'secondary',
  // Medication / Prescription
  ACTIVE: 'success',
  INACTIVE: 'secondary',
  DISPENSED: 'success',
  EXPIRED: 'dark',
  // Lab / Radiology results
  READY: 'success',
  VALIDATED: 'info',
  // Surgery
  PLANNED: 'info',
  PERFORMED: 'success',
  DELAYED: 'warning',
  // Admission / Bed
  AVAILABLE: 'success',
  OCCUPIED: 'danger',
  RESERVED: 'warning',
  CLEANING: 'info',
  OUT_OF_ORDER: 'secondary',
  ADMITTED: 'primary',
  DISCHARGED: 'success',
  DECEASED: 'dark',
  // Tasks & Projects
  PLANNING: 'info',
  ON_HOLD: 'secondary',
};

// =============================================================================
// Arabic labels
// =============================================================================
window.ENUMS.LABELS = {
  // Visit states
  OPEN: 'مفتوحة',
  CHECKED_IN: 'تم تسجيل الدخول',
  IN_PROGRESS: 'قيد التنفيذ',
  COMPLETED: 'مكتملة',
  ARCHIVED: 'مؤرشفة',
  CANCELLED: 'ملغية',
  NO_SHOW: 'لم يحضر',
  // Visit types
  REGULAR: 'زيارة عادية',
  FOLLOW_UP: 'متابعة',
  CONSULTATION: 'استشارة',
  EMERGENCY: 'طوارئ',
  // Appointment states
  SCHEDULED: 'مجدول',
  CONFIRMED: 'مؤكد',
  DONE: 'تم',
  // Order states
  REQUESTED: 'مطلوب',
  RECEIVED: 'تم الاستلام',
  ANALYZING: 'قيد التحليل',
  REVIEWED: 'تمت المراجعة',
  APPROVED: 'معتمد',
  DRAFT: 'مسودة',
  ORDERED: 'مطلوب',
  SAMPLE_COLLECTED: 'تم أخذ العينة',
  RESULTS_ENTERED: 'تم إدخال النتائج',
  DELIVERED: 'تم التسليم',
  IMAGES_CAPTURED: 'تم التقاط الصور',
  REPORTED: 'تم التقرير',
  // Billing states
  PENDING: 'قيد الانتظار',
  PAID: 'مدفوع',
  PARTIAL: 'مدفوع جزئياً',
  DEBT: 'ديون',
  REFUNDED: 'مسترجع',
  POSTED: 'مرسل',
  ISSUED: 'صادر',
  VOID: 'ملغي',
  // Emergency states
  NEW: 'جديد',
  WAITING: 'انتظار',
  TRIAGE: 'فرز',
  RESUSCITATION: 'إنعاش',
  TREATMENT: 'علاج',
  OBSERVATION: 'مراقبة',
  TRANSFERRED: 'محول',
  // Emergency severity
  LOW: 'منخفض',
  MODERATE: 'متوسط',
  HIGH: 'عالي',
  CRITICAL: 'حرج',
  // Queue states
  CALLED: 'تم النداء',
  SKIPPED: 'تم التخطي',
  // Medication / Prescription
  ACTIVE: 'نشط',
  INACTIVE: 'غير نشط',
  DISCONTINUED: 'موقوف',
  DISPENSED: 'تم الصرف',
  EXPIRED: 'منتهي الصلاحية',
  // Lab / Radiology results
  READY: 'جاهز',
  VALIDATED: 'معتمد',
  // Surgery
  PLANNED: 'مخطط',
  PERFORMED: 'تم',
  DELAYED: 'مؤجل',
  // Admission / Bed
  AVAILABLE: 'متاح',
  OCCUPIED: 'مشغول',
  RESERVED: 'محجوز',
  CLEANING: 'تنظيف',
  OUT_OF_ORDER: 'عطل',
  ADMITTED: 'تم الإدخال',
  DISCHARGED: 'تم الخروج',
  DECEASED: 'متوفي',
  // Referral
  ROUTINE: 'روتيني',
  URGENT: 'عاجل',
  STAT: 'فوري',
  SENT: 'مرسل',
  ACCEPTED: 'مقبول',
  DECLINED: 'مرفوض',
  // Permission levels
  READ: 'قراءة',
  WRITE: 'كتابة',
  DELETE: 'حذف',
  ADMIN: 'إدارة',
  SUPER_ADMIN: 'إدارة عليا',
  // Permission categories
  USER_MANAGEMENT: 'إدارة المستخدمين',
  PATIENT_MANAGEMENT: 'إدارة المرضى',
  MEDICAL_RECORDS: 'السجلات الطبية',
  FINANCIAL: 'النظام المالي',
  SYSTEM_ADMIN: 'إدارة النظام',
  BACKUP_RESTORE: 'النسخ الاحتياطي',
  REPORTS: 'التقارير',
  SETTINGS: 'الإعدادات',
  SECURITY: 'الأمان',
  AUDIT: 'التدقيق',
  // Tasks & Projects
  PLANNING: 'تخطيط',
  ON_HOLD: 'معلق',
};
