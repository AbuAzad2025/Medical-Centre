#!/usr/bin/env python3
"""Create CPT and LOINC CSV terminology files for the medical platform."""
import csv
from pathlib import Path

OUTPUT_DIR = Path("data/terminology")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# CPT codes (5-digit, valid format)
CPT_CODES = [
    ("99213", "Office Visit - Established Patient", "الاستشارة (مريض مسجل)", "E/M"),
    ("99214", "Office Visit - Established Patient Detailed", "الاستشارة (مريض مسجل - تفصيلية)", "E/M"),
    ("99215", "Office Visit - Established Patient Complex", "الاستشارة (مريض مسجل - معقدة)", "E/M"),
    ("99203", "New Patient Office Visit", "الاستشارة (مريض جديد)", "E/M"),
    ("99204", "New Patient Office Visit Detailed", "الاستشارة (مريض جديد - تفصيلية)", "E/M"),
    ("99205", "New Patient Office Visit Complex", "الاستشارة (مريض جديد - معقدة)", "E/M"),
    ("99281", "Emergency Department Visit", "زيارة قسم الطوارئ", "Emergency"),
    ("99282", "Emergency Department Visit Expanded", "زيارة قسم الطوارئ (موسع)", "Emergency"),
    ("99283", "Emergency Department Visit Detailed", "زيارة قسم الطوارئ (تفصيلية)", "Emergency"),
    ("99284", "Emergency Department Visit Complex", "زيارة قسم الطوارئ (معقدة)", "Emergency"),
    ("99285", "Emergency Department Visit Critical", "زيارة قسم الطوارئ (حرجة)", "Emergency"),
    ("99238", "Hospital Discharge Day Management", "إدارة يوم الخروج من المستشفى", "Inpatient"),
    ("99239", "Hospital Discharge Day Management Complex", "إدارة يوم الخروج من المستشفى (معقدة)", "Inpatient"),
    ("99221", "Initial Hospital Care", "رعاية مستشفى أولية", "Inpatient"),
    ("99222", "Initial Hospital Care Detailed", "رعاية مستشفى أولية (تفصيلية)", "Inpatient"),
    ("99223", "Initial Hospital Care Complex", "رعاية مستشفى أولية (معقدة)", "Inpatient"),
    ("99231", "Subsequent Hospital Care", "رعاية مستشفى لاحقة", "Inpatient"),
    ("99232", "Subsequent Hospital Care Detailed", "رعاية مستشفى لاحقة (تفصيلية)", "Inpatient"),
    ("99233", "Subsequent Hospital Care Complex", "رعاية مستشفى لاحقة (معقدة)", "Inpatient"),
    ("99291", "Critical Care First Hour", "رعاية حرجة (ساعة أولى)", "Critical Care"),
    ("99292", "Critical Care Additional 30 min", "رعاية حرجة (30 دقيقة إضافية)", "Critical Care"),
    ("99460", "Initial Hospital Care Newborn", "رعاية مستشفى أولية - حديث ولادة", "Newborn"),
    ("99461", "Initial Hospital Care Newborn Intensive", "رعاية مستشفى أولية - حديث ولادة (مكثفة)", "Newborn"),
    ("99462", "Subsequent Hospital Care Newborn", "رعاية مستشفى لاحقة - حديث ولادة", "Newborn"),
    ("99463", "Subsequent Hospital Care Newborn Intensive", "رعاية مستشفى لاحقة - حديث ولادة (مكثفة)", "Newborn"),
]

# LOINC codes (valid check digits)
LOINC_CODES = [
    ("718-7", "Hemoglobin", "هيموگلوبين", "Hematology"),
    ("2345-7", "Glucose", "گلوكوز", "Chemistry"),
    ("4548-4", "HbA1c", "HbA1c", "Chemistry"),
    ("2093-3", "Cholesterol", "كوليسترول", "Chemistry"),
    ("2571-8", "Triglycerides", "ثلاثي گليسريد", "Chemistry"),
    ("2085-9", "HDL Cholesterol", "HDL كوليسترول", "Chemistry"),
    ("2089-1", "LDL Cholesterol", "LDL كوليسترول", "Chemistry"),
    ("1742-6", "ALT", "ALT", "Chemistry"),
    ("1920-8", "AST", "AST", "Chemistry"),
    ("1975-2", "Bilirubin Total", "بيليروبين كلي", "Chemistry"),
    ("2160-0", "Creatinine", "كرياتينين", "Chemistry"),
    ("3094-0", "BUN", "BUN", "Chemistry"),
    ("2823-3", "Potassium", "بوتاسيوم", "Chemistry"),
    ("2951-2", "Sodium", "صوديوم", "Chemistry"),
    ("2075-0", "Chloride", "كلوريد", "Chemistry"),
    ("2028-9", "CO2", "CO2", "Chemistry"),
    ("1988-5", "CRP", "CRP", "Immunology"),
    ("30522-7", "ESR", "ESR", "Hematology"),
    ("789-8", "RBC", "RBC", "Hematology"),
    ("6690-2", "WBC", "WBC", "Hematology"),
    ("777-3", "Platelets", "صفائح", "Hematology"),
    ("787-2", "MCV", "MCV", "Hematology"),
    ("785-6", "MCH", "MCH", "Hematology"),
    ("786-4", "MCHC", "MCHC", "Hematology"),
    ("14647-2", "Cholesterol/HDL Ratio", "نسبة كوليسترول/HDL", "Chemistry"),
    ("10839-9", "Troponin I", "Troponin I", "Cardiac"),
    ("10839-9", "Troponin I", "Troponin I", "Cardiac"),
    ("48066-5", "D-Dimer", "D-Dimer", "Hematology"),
    ("5902-2", "Prothrombin Time", "وقت بروترومبين", "Coagulation"),
    ("6301-6", "INR", "INR", "Coagulation"),
    ("3173-2", "aPTT", "aPTT", "Coagulation"),
    ("14959-1", "Microalbumin", "Microalbumin", "Chemistry"),
    ("1989-3", "Vitamin D", "فيتامين D", "Vitamin"),
    ("2132-9", "Vitamin B12", "فيتامين B12", "Vitamin"),
    ("2276-4", "Ferritin", "Ferritin", "Iron"),
    ("2498-4", "Iron", "حديد", "Iron"),
    ("2500-7", "TIBC", "TIBC", "Iron"),
    ("1986-9", "Insulin", "إنسولين", "Endocrinology"),
    ("20448-7", "Cortisol", "Cortisol", "Endocrinology"),
    ("11580-8", "Prolactin", "Prolactin", "Endocrinology"),
    ("1668-3", "Alkaline Phosphatase", "Alkaline Phosphatase", "Chemistry"),
    ("2324-2", "Gamma GT", "Gamma GT", "Chemistry"),
    ("1994-3", "Calcium", "كالسيوم", "Chemistry"),
    ("2885-2", "Protein Total", "بروتين كلي", "Chemistry"),
    ("2888-6", "Albumin", "Albumin", "Chemistry"),
    ("1751-7", "Albumin/Globulin Ratio", "نسبة Albumin/Globulin", "Chemistry"),
    ("2886-0", "Globulin", "Globulin", "Chemistry"),
    ("1995-0", "Magnesium", "مغنيسيوم", "Chemistry"),
    ("1990-1", "Ammonia", "أمونيا", "Chemistry"),
    ("2157-6", "CK", "CK", "Chemistry"),
    ("2093-3", "Cholesterol", "كوليسترول", "Chemistry"),
]

# Write CPT CSV
cpt_path = OUTPUT_DIR / "cpt_codes.csv"
with open(cpt_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['system', 'code', 'description', 'description_ar', 'category'])
    for code, name, name_ar, category in CPT_CODES:
        writer.writerow(['CPT', code, name, name_ar, category])

# Write LOINC CSV
loinc_path = OUTPUT_DIR / "loinc_codes.csv"
with open(loinc_path, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['system', 'code', 'description', 'description_ar', 'category'])
    for code, name, name_ar, category in LOINC_CODES:
        writer.writerow(['LOINC', code, name, name_ar, category])

print(f"Created CPT CSV: {cpt_path} ({len(CPT_CODES)} codes)")
print(f"Created LOINC CSV: {loinc_path} ({len(LOINC_CODES)} codes)")
print(f"\nTo load: set TERMINOLOGY_PATH={OUTPUT_DIR}")
