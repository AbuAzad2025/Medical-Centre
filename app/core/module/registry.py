"""
Module Registry — single source of truth for all platform modules
"""
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class ModuleMeta:
    name: str
    name_ar: str
    category: str  # clinical | administrative | financial | integration
    required_modules: tuple
    icon: str
    description_ar: str

# Central registry — hardcoded, version-controlled
MODULE_REGISTRY: Dict[str, ModuleMeta] = {
    "reception": ModuleMeta(
        name="reception",
        name_ar="الاستقبال",
        category="administrative",
        required_modules=(),
        icon="fas fa-user-plus",
        description_ar="تسجيل المرضى والزيارات والمواعيد",
    ),
    "doctor": ModuleMeta(
        name="doctor",
        name_ar="الأطباء",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-user-md",
        description_ar="الفحوصات والتشخيص والروشيتات",
    ),
    "lab": ModuleMeta(
        name="lab",
        name_ar="المختبر",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-flask",
        description_ar="طلبات التحاليل وإدخال النتائج",
    ),
    "radiology": ModuleMeta(
        name="radiology",
        name_ar="الأشعة",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-x-ray",
        description_ar="طلبات الأشعة والتقارير",
    ),
    "pharmacy": ModuleMeta(
        name="pharmacy",
        name_ar="الصيدلية",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-pills",
        description_ar="إدارة الأدوية والمخزون والصرف",
    ),
    "emergency": ModuleMeta(
        name="emergency",
        name_ar="الطوارئ",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-ambulance",
        description_ar="حالات الطوارئ والأولوية",
    ),
    "nursing": ModuleMeta(
        name="nursing",
        name_ar="التمريض",
        category="clinical",
        required_modules=("reception",),
        icon="fas fa-user-nurse",
        description_ar="رعاية المرضى والعلاجات",
    ),
    "billing": ModuleMeta(
        name="billing",
        name_ar="الفوترة",
        category="financial",
        required_modules=("reception",),
        icon="fas fa-file-invoice-dollar",
        description_ar="الفواتير والدفعات والتأمين",
    ),
    "inventory": ModuleMeta(
        name="inventory",
        name_ar="المخزون",
        category="administrative",
        required_modules=("reception",),
        icon="fas fa-boxes",
        description_ar="المستودعات والمشتريات",
    ),
    "appointments": ModuleMeta(
        name="appointments",
        name_ar="المواعيد",
        category="administrative",
        required_modules=("reception",),
        icon="fas fa-calendar-alt",
        description_ar="جدولة المواعيد والتذكير",
    ),
    "reporting": ModuleMeta(
        name="reporting",
        name_ar="التقارير",
        category="administrative",
        required_modules=(),
        icon="fas fa-chart-bar",
        description_ar="التقارير الطبية والمالية والإدارية",
    ),
    "owner": ModuleMeta(
        name="owner",
        name_ar="المالك",
        category="integration",
        required_modules=(),
        icon="fas fa-crown",
        description_ar="لوحة تحكم المالك والمنصة السحابية",
    ),
}

def get_module_metadata(name: str) -> ModuleMeta | None:
    return MODULE_REGISTRY.get(name)

def get_all_module_names() -> List[str]:
    return list(MODULE_REGISTRY.keys())

def get_clinical_modules() -> List[str]:
    return [m.name for m in MODULE_REGISTRY.values() if m.category == "clinical"]
