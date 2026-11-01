#!/usr/bin/env python3
"""Create a basic CPT/LOINC terminology file for the medical platform."""
import json
from pathlib import Path

# Basic CPT codes (Common Procedural Terminology)
CPT_CODES = [
    {"code": "99213", "name": "Office Visit - Established Patient", "name_ar": "زيارة مكتب - مريض مسجل", "category": "E/M", "price": 50.0},
    {"code": "99214", "name": "Office Visit - Established Patient (Detailed)", "name_ar": "زيارة مكتب - مريض مسجل (تفصيلية)", "category": "E/M", "price": 75.0},
    {"code": "99215", "name": "Office Visit - Established Patient (Complex)", "name_ar": "زيارة مكتب - مريض مسجل (معقدة)", "category": "E/M", "price": 100.0},
    {"code": "99203", "name": "New Patient Office Visit", "name_ar": "زيارة مكتب - مريض جديد", "category": "E/M", "price": 80.0},
    {"code": "99204", "name": "New Patient Office Visit (Detailed)", "name_ar": "زيارة مكتب - مريض جديد (تفصيلية)", "category": "E/M", "price": 120.0},
    {"code": "99205", "name": "New Patient Office Visit (Complex)", "name_ar": "زيارة مكتب - مريض جديد (معقدة)", "category": "E/M", "price": 150.0},
    {"code": "99281", "name": "Emergency Department Visit", "name_ar": "زيارة قسم الطوارئ", "category": "Emergency", "price": 100.0},
    {"code": "99282", "name": "Emergency Department Visit (Expanded)", "name_ar": "زيارة قسم الطوارئ (موسع)", "category": "Emergency", "price": 150.0},
    {"code": "99283", "name": "Emergency Department Visit (Detailed)", "name_ar": "زيارة قسم الطوارئ (تفصيلية)", "category": "Emergency", "price": 200.0},
    {"code": "99284", "name": "Emergency Department Visit (Complex)", "name_ar": "زيارة قسم الطوارئ (معقدة)", "category": "Emergency", "price": 250.0},
    {"code": "99285", "name": "Emergency Department Visit (Critical)", "name_ar": "زيارة قسم الطوارئ (حرجة)", "category": "Emergency", "price": 300.0},
    {"code": "99238", "name": "Hospital Discharge Day Management", "name_ar": "إدارة يوم الخروج من المستشفى", "category": "Inpatient", "price": 75.0},
    {"code": "99239", "name": "Hospital Discharge Day Management (Complex)", "name_ar": "إدارة يوم الخروج من المستشفى (معقدة)", "category": "Inpatient", "price": 100.0},
    {"code": "99221", "name": "Initial Hospital Care", "name_ar": "رعاية مستشفى أولية", "category": "Inpatient", "price": 150.0},
    {"code": "99222", "name": "Initial Hospital Care (Detailed)", "name_ar": "رعاية مستشفى أولية (تفصيلية)", "category": "Inpatient", "price": 200.0},
    {"code": "99223", "name": "Initial Hospital Care (Complex)", "name_ar": "رعاية مستشفى أولية (معقدة)", "category": "Inpatient", "price": 250.0},
    {"code": "99231", "name": "Subsequent Hospital Care", "name_ar": "رعاية مستشفى لاحقة", "category": "Inpatient", "price": 60.0},
    {"code": "99232", "name": "Subsequent Hospital Care (Detailed)", "name_ar": "رعاية مستشفى لاحقة (تفصيلية)", "category": "Inpatient", "price": 90.0},
    {"code": "99233", "name": "Subsequent Hospital Care (Complex)", "name_ar": "رعاية مستشفى لاحقة (معقدة)", "category": "Inpatient", "price": 120.0},
    {"code": "99291", "name": "Critical Care (First Hour)", "name_ar": "رعاية حرجة (ساعة أولى)", "category": "Critical Care", "price": 300.0},
    {"code": "99292", "name": "Critical Care (Additional 30 min)", "name_ar": "رعاية حرجة (30 دقيقة إضافية)", "category": "Critical Care", "price": 150.0},
    {"code": "99460", "name": "Initial Hospital Care - Newborn", "name_ar": "رعاية مستشفى أولية - حديث ولادة", "category": "Newborn", "price": 100.0},
    {"code": "99461", "name": "Initial Hospital Care - Newborn (Intensive)", "name_ar": "رعاية مستشفى أولية - حديث ولادة (مكثفة)", "category": "Newborn", "price": 150.0},
    {"code": "99462", "name": "Subsequent Hospital Care - Newborn", "name_ar": "رعاية مستشفى لاحقة - حديث ولادة", "category": "Newborn", "price": 75.0},
    {"code": "99463", "name": "Subsequent Hospital Care - Newborn (Intensive)", "name_ar": "رعاية مستشفى لاحقة - حديث ولادة (مكثفة)", "category": "Newborn", "price": 100.0},
]

# Basic LOINC codes
LOINC_CODES = [
    {"code": "2339-0", "name": "Glucose", "name_ar": "گلوكوز", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2345-7", "name": "Glucose (Fasting)", "name_ar": "گلوكوز (صائم)", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "4548-4", "name": "HbA1c", "name_ar": "HbA1c", "category": "Chemistry", "unit": "%"},
    {"code": "2093-3", "name": "Cholesterol", "name_ar": "كوليسترول", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2571-8", "name": "Triglycerides", "name_ar": "ثلاثي گليسريد", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2085-9", "name": "HDL Cholesterol", "name_ar": "HDL كوليسترول", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2089-1", "name": "LDL Cholesterol", "name_ar": "LDL كوليسترول", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "1742-6", "name": "ALT", "name_ar": "ALT", "category": "Chemistry", "unit": "U/L"},
    {"code": "1920-8", "name": "AST", "name_ar": "AST", "category": "Chemistry", "unit": "U/L"},
    {"code": "1975-2", "name": "Bilirubin Total", "name_ar": "بيليروبين كلي", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2160-0", "name": "Creatinine", "name_ar": "كرياتينين", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "3094-0", "name": "BUN", "name_ar": "BUN", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2823-3", "name": "Potassium", "name_ar": "بوتاسيوم", "category": "Chemistry", "unit": "mEq/L"},
    {"code": "2951-2", "name": "Sodium", "name_ar": "صوديوم", "category": "Chemistry", "unit": "mEq/L"},
    {"code": "2075-0", "name": "Chloride", "name_ar": "كلوريد", "category": "Chemistry", "unit": "mEq/L"},
    {"code": "2028-9", "name": "CO2", "name_ar": "CO2", "category": "Chemistry", "unit": "mEq/L"},
    {"code": "1988-5", "name": "CRP", "name_ar": "CRP", "category": "Immunology", "unit": "mg/L"},
    {"code": "30522-7", "name": "ESR", "name_ar": "ESR", "category": "Hematology", "unit": "mm/hr"},
    {"code": "718-7", "name": "Hemoglobin", "name_ar": "هيموگلوبين", "category": "Hematology", "unit": "g/dL"},
    {"code": "789-8", "name": "RBC", "name_ar": "RBC", "category": "Hematology", "unit": "million/uL"},
    {"code": "6690-2", "name": "WBC", "name_ar": "WBC", "category": "Hematology", "unit": "thousand/uL"},
    {"code": "777-3", "name": "Platelets", "name_ar": "صفائح", "category": "Hematology", "unit": "thousand/uL"},
    {"code": "787-2", "name": "MCV", "name_ar": "MCV", "category": "Hematology", "unit": "fL"},
    {"code": "785-6", "name": "MCH", "name_ar": "MCH", "category": "Hematology", "unit": "pg"},
    {"code": "786-4", "name": "MCHC", "name_ar": "MCHC", "category": "Hematology", "unit": "g/dL"},
    {"code": "2157-6", "name": "CK (Creatine Kinase)", "name_ar": "CK (كرياتين كيناز)", "category": "Chemistry", "unit": "U/L"},
    {"code": "14647-2", "name": "Cholesterol/HDL Ratio", "name_ar": "نسبة كوليسترول/HDL", "category": "Chemistry", "unit": "ratio"},
    {"code": "10839-9", "name": "Troponin I", "name_ar": "Troponin I", "category": "Cardiac", "unit": "ng/mL"},
    {"code": "30240-2", "name": "Troponin T", "name_ar": "Troponin T", "category": "Cardiac", "unit": "ng/mL"},
    {"code": "48066-5", "name": "D-Dimer", "name_ar": "D-Dimer", "category": "Hematology", "unit": "ng/mL"},
    {"code": "5902-2", "name": "Prothrombin Time", "name_ar": "وقت بروترومبين", "category": "Coagulation", "unit": "seconds"},
    {"code": "6301-6", "name": "INR", "name_ar": "INR", "category": "Coagulation", "unit": "ratio"},
    {"code": "3173-2", "name": "aPTT", "name_ar": "aPTT", "category": "Coagulation", "unit": "seconds"},
    {"code": "14959-1", "name": "Microalbumin", "name_ar": "Microalbumin", "category": "Chemistry", "unit": "mg/L"},
    {"code": "2106-3", "name": "Tyrosine", "name_ar": "Tyrosine", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "1989-3", "name": "Vitamin D", "name_ar": "فيتامين D", "category": "Vitamin", "unit": "ng/mL"},
    {"code": "2132-9", "name": "Vitamin B12", "name_ar": "فيتامين B12", "category": "Vitamin", "unit": "pg/mL"},
    {"code": "2276-4", "name": "Ferritin", "name_ar": "Ferritin", "category": "Iron", "unit": "ng/mL"},
    {"code": "2498-4", "name": "Iron", "name_ar": "حديد", "category": "Iron", "unit": "mcg/dL"},
    {"code": "2500-7", "name": "TIBC", "name_ar": "TIBC", "category": "Iron", "unit": "mcg/dL"},
    {"code": "1986-9", "name": "Insulin", "name_ar": "إنسولين", "category": "Endocrinology", "unit": "uIU/mL"},
    {"code": "20448-7", "name": "Cortisol", "name_ar": "Cortisol", "category": "Endocrinology", "unit": "mcg/dL"},
    {"code": "11580-8", "name": "Prolactin", "name_ar": "Prolactin", "category": "Endocrinology", "unit": "ng/mL"},
    {"code": "1668-3", "name": "Alkaline Phosphatase", "name_ar": "Alkaline Phosphatase", "category": "Chemistry", "unit": "U/L"},
    {"code": "2324-2", "name": "Gamma GT", "name_ar": "Gamma GT", "category": "Chemistry", "unit": "U/L"},
    {"code": "1994-3", "name": "Calcium", "name_ar": "كالسيوم", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2885-2", "name": "Protein Total", "name_ar": "بروتين كلي", "category": "Chemistry", "unit": "g/dL"},
    {"code": "2888-6", "name": "Albumin", "name_ar": "Albumin", "category": "Chemistry", "unit": "g/dL"},
    {"code": "1751-7", "name": "Albumin/Globulin Ratio", "name_ar": "نسبة Albumin/Globulin", "category": "Chemistry", "unit": "ratio"},
    {"code": "2886-0", "name": "Globulin", "name_ar": "Globulin", "category": "Chemistry", "unit": "g/dL"},
    {"code": "5803-2", "name": "AST/ALT Ratio", "name_ar": "نسبة AST/ALT", "category": "Chemistry", "unit": "ratio"},
    {"code": "1995-0", "name": "Magnesium", "name_ar": "مغنيسيوم", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2823-3", "name": "Phosphorus", "name_ar": "فوسفور", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "2777-1", "name": "Phosphorus", "name_ar": "فوسفور", "category": "Chemistry", "unit": "mg/dL"},
    {"code": "1990-1", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1991-9", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1992-7", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1993-5", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1996-8", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1997-6", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1998-4", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "1999-2", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "2000-8", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
    {"code": "2001-6", "name": "Ammonia", "name_ar": "أمونيا", "category": "Chemistry", "unit": "mcg/dL"},
]

output = {
    "cpt_codes": CPT_CODES,
    "loinc_codes": LOINC_CODES,
    "version": "1.0",
    "source": "AZAD Medical Centre Platform - Basic Terminology",
    "note": "Basic CPT/LOINC codes for development. Replace with official release for production."
}

output_path = Path("data/terminology/basic_terminology.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')

print(f"Created terminology file: {output_path}")
print(f"CPT codes: {len(CPT_CODES)}")
print(f"LOINC codes: {len(LOINC_CODES)}")
