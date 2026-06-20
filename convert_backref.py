"""
Convert all `backref` to `back_populates` across all model files.
Phase 2.2 of the field relationship fix plan.
"""
import re
import os
from collections import defaultdict

MODELS_DIR = r'D:\Data\MED-2-7-2025\medical_system\models'

# ============================================================
# Phase 1: Build class_name -> file_path mapping
# ============================================================
class_to_file = {}
file_to_classes = {}

for fname in os.listdir(MODELS_DIR):
    if not fname.endswith('.py'):
        continue
    fpath = os.path.join(MODELS_DIR, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    classes = []
    for m in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
        cn = m.group(1)
        class_to_file[cn] = fpath
        classes.append(cn)
    file_to_classes[fpath] = classes

# Aliases / known mappings for models with unusual names
MODEL_ALIASES = {
    'User': 'User', 'Patient': 'Patient', 'Visit': 'Visit',
    'Department': 'Department', 'Nurse': 'Nurse',
    'MedicalRecord': 'MedicalRecord', 'Treatment': 'Treatment',
    'Prescription': 'Prescription', 'Medication': 'Medication',
    'Admission': 'Admission', 'DRGCode': 'DRGCode',
    'Appointment': 'Appointment', 'OnlineBooking': 'OnlineBooking',
    'WorkflowStep': 'WorkflowStep', 'PatientWorkflow': 'PatientWorkflow',
    'WorkflowQueueItem': 'WorkflowQueueItem', 'WorkflowTransfer': 'WorkflowTransfer',
    'WorkflowEvent': 'WorkflowEvent', 'Nurse': 'Nurse',
    'Ward': 'Ward', 'Room': 'Room', 'Bed': 'Bed',
    'SurgerySchedule': 'SurgerySchedule', 'SurgeryChecklist': 'SurgeryChecklist',
    'ICD10Code': 'ICD10Code', 'CPTCode': 'CPTCode',
    'CodedDiagnosis': 'CodedDiagnosis', 'CodedProcedure': 'CodedProcedure',
    'Barcode': 'Barcode', 'BarcodeScanLog': 'BarcodeScanLog',
    'Vaccine': 'Vaccine', 'Immunization': 'Immunization',
    'VaccinationSchedule': 'VaccinationSchedule',
    'Referral': 'Referral',
    'QueueItem': 'QueueItem', 'QueueSettings': 'QueueSettings',
    'Report': 'Report', 'ReportExecution': 'ReportExecution', 'ReportTemplate': 'ReportTemplate',
    'DICOMStudy': 'DICOMStudy', 'DICOMSeries': 'DICOMSeries', 'DICOMInstance': 'DICOMInstance',
    'ClinicalPathway': 'ClinicalPathway', 'ClinicalPathwayStep': 'ClinicalPathwayStep',
    'PatientCarePlan': 'PatientCarePlan', 'CarePlanTask': 'CarePlanTask',
    'PrescriptionItem': 'PrescriptionItem', 'PrescriptionDispenseLog': 'PrescriptionDispenseLog',
    'PharmacySale': 'PharmacySale',
    'StaffSchedule': 'StaffSchedule', 'StaffAbsence': 'StaffAbsence',
    'Allergy': 'Allergy', 'Problem': 'Problem', 'AllergyIntolerance': 'AllergyIntolerance',
    'DigitalSignature': 'DigitalSignature', 'SessionLog': 'SessionLog',
    'CDSRule': 'CDSRule', 'CDSFiredAlert': 'CDSFiredAlert',
    'EMARAdministration': 'EMARAdministration', 'EMARSchedule': 'EMARSchedule',
    'MedicationReconciliation': 'MedicationReconciliation',
    'NotificationQueue': 'NotificationQueue', 'NotificationTemplate': 'NotificationTemplate',
    'PatientWorkflowStep': 'PatientWorkflowStep',
    'PricingManagement': 'PricingManagement', 'PricingRule': 'PricingRule',
    'Branding': 'Branding',
    'PerformanceAnalytics': 'PerformanceAnalytics',
    'PatientInsight': 'PatientInsight',
    'ModelPrediction': 'ModelPrediction',
    'DentalChart': 'DentalChart', 'DentalTooth': 'DentalTooth',
    'FHIRPatientMapping': 'FHIRPatientMapping',
}

def resolve_model_file(model_name):
    """Find the file path for a model class name."""
    # Strip leading/trailing quotes if present
    model_name = model_name.strip("'\"")
    if model_name in class_to_file:
        return class_to_file[model_name]
    if model_name in MODEL_ALIASES:
        resolved = MODEL_ALIASES[model_name]
        if resolved in class_to_file:
            return class_to_file[resolved]
    return None

def get_class_indent_and_lines(content, class_name):
    """Find the class definition and its line range."""
    # Find class definition
    pattern = rf'^class\s+{re.escape(class_name)}\b'
    for m in re.finditer(pattern, content, re.MULTILINE):
        start = m.start()
        # Find the ':' that ends the class declaration
        colon_pos = content.find(':', start)
        if colon_pos == -1:
            continue
        class_decl_end = colon_pos + 1
        
        # Get the indentation of the class body (first non-empty line after ':')
        rest = content[class_decl_end:].lstrip('\n')
        if not rest:
            return start, len(content), ''
        next_lines = content[class_decl_end:].split('\n')
        base_indent = ''
        for line in next_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                base_indent = line[:len(line) - len(line.lstrip())]
                break
        
        # Find end of class: next top-level class or def (at column 0) after class_decl_end
        # or end of file
        end_pos = len(content)
        # Search from class_decl_end for next 'class ' or 'def ' at column 0
        search_content = content[class_decl_end:]
        for match in re.finditer(r'\n(class|def)\s', search_content):
            match_pos = class_decl_end + match.start() + 1  # +1 for the \n
            # Make sure this is at column 0 (no leading whitespace on the line)
            line_start = content.rfind('\n', 0, match_pos) + 1
            if content[line_start:match_pos].strip() == content[line_start:match_pos]:
                # No leading whitespace, this is a top-level definition
                end_pos = match_pos
                break
        
        return start, end_pos, base_indent
    return None, None, ''

def add_relationship_to_model(content, class_name, new_rel_line):
    """Add a relationship line to a model class, finding the right insertion point."""
    start, end, base_indent = get_class_indent_and_lines(content, class_name)
    if start is None:
        return content, False
    
        # Look for an existing relationships section (relationships / العلاقات)
    class_body = content[start:end]
    
    # Try to find after existing relationships section or before __repr__ / first method
    insert_points = []
    
    # Pattern 1: After a comment indicating relationships
    for pat in [r'#\s*relationships?', r'#\s*Relationships?', r'#\s*relationships?\s*$']:
        for m in re.finditer(pat, class_body, re.IGNORECASE | re.MULTILINE):
            # Find the next non-empty line after this comment
            after = class_body[m.end():]
            lines = after.split('\n')
            offset = 0
            for line in lines:
                offset += len(line) + 1
                if line.strip() and not line.strip().startswith('#'):
                    insert_points.append((start + m.end() + offset - len(line) - 1, 'after_existing_rel'))
                    break
    
    # Pattern 2: Before __repr__ or first method
    for m in re.finditer(r'^\s+def\s+__repr__', class_body, re.MULTILINE):
        insert_points.append((start + m.start(), 'before_repr'))
        break
    
    if not insert_points:
        # Pattern 3: Before any method
        for m in re.finditer(r'^\s+def\s+\w+', class_body, re.MULTILINE):
            insert_points.append((start + m.start(), 'before_method'))
            break
    
    if not insert_points:
        # Add at the end of class body (before last dedent)
        insert_points.append((end - 1, 'end'))
    
    # Use the first insertion point (prefer after relationships section)
    insert_points.sort(key=lambda x: x[0])
    # Prefer 'after_existing_rel' if available, then 'before_repr', etc.
    preferred = [p for p in insert_points if p[1] == 'after_existing_rel']
    if not preferred:
        preferred = [p for p in insert_points if p[1] == 'before_repr']
    if not preferred:
        preferred = [p for p in insert_points if p[1] == 'before_method']
    if not preferred:
        preferred = [insert_points[0]]
    
    insert_pos = preferred[0][0]
    
    # Determine indentation for the new line
    # Look at the line where we're inserting
    line_start = content.rfind('\n', 0, insert_pos)
    if line_start == -1:
        line_start = 0
    current_line = content[line_start:insert_pos]
    
    if preferred[0][1] == 'after_existing_rel':
        # Indent same as the existing relationship
        indent_match = re.match(r'^(\s+)', current_line)
        indent = indent_match.group(1) if indent_match else '    '
        # Insert after the existing relationship line (add newline + our line)
        new_content = content[:insert_pos] + '\n' + indent + new_rel_line + content[insert_pos:]
    else:
        # Use base_indent + 4 spaces
        indent = base_indent + '    ' if base_indent else '    '
        new_content = content[:insert_pos] + indent + new_rel_line + '\n\n' + content[insert_pos:]
    
    return new_content, True

# ============================================================
# Phase 2: Find all relationship() calls with backref
# ============================================================

# We'll collect backref info: (source_file, source_class, source_attr, target_model, backref_name, extra_kwargs)
backrefs = []

# Track files we need to modify and their new content
file_edits = defaultdict(list)  # filepath -> [(old_str, new_str)]
reverse_rels = []  # (target_model, source_model, backref_name, source_attr, extra_kwargs)

for fname in sorted(os.listdir(MODELS_DIR)):
    if not fname.endswith('.py'):
        continue
    fpath = os.path.join(MODELS_DIR, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all classes in this file
    classes_in_file = file_to_classes.get(fpath, [])
    
    # For each class, find relationship() calls with backref
    for class_name in classes_in_file:
        class_start, class_end, _ = get_class_indent_and_lines(content, class_name)
        if class_start is None:
            print(f"  WARNING: Could not find class {class_name} in {fname}")
            continue
        class_body = content[class_start:class_end]
        print(f"  Processing {class_name}: body_len={len(class_body)}")
        
        # Pattern to match: attr = db.relationship(...) possibly multi-line
        # We need to be careful with nested parentheses
        # Simple approach: find `= db.relationship(` and match balanced parens
        rel_pattern = r'(\w+)\s*=\s*db\.relationship\('
        
        for m in re.finditer(rel_pattern, class_body):
            attr_name = m.group(1)
            paren_start = class_start + m.end() - 1  # position of '('
            
            # Find matching closing paren, handling nested parens
            depth = 1
            pos = paren_start + 1
            while depth > 0 and pos < len(content):
                if content[pos] == '(':
                    depth += 1
                elif content[pos] == ')':
                    depth -= 1
                pos += 1
            paren_end = pos - 1
            
            rel_call = content[paren_start:paren_end + 1]
            
            # Check if this has backref
            if 'backref' not in rel_call:
                continue
            
            print(f"    BACKREF FOUND: {class_name}.{attr_name} -> {rel_call[:100]}")
            
            # Extract target model name (first string argument)
            # rel_call is the content inside db.relationship(...), so it starts with ('ModelName' or ("ModelName"
            target_match = re.search(r"^\s*\('(\w+)'", rel_call)
            if not target_match:
                target_match = re.search(r'^\s*\("(\w+)"', rel_call)
            if not target_match:
                print(f"      ERROR: Could not extract target model from: {rel_call[:100]}")
                continue
            target_model = target_match.group(1)
            print(f"      Target model: {target_model}")
            
            # Extract backref name
            backref_match = re.search(r"backref\s*=\s*'(\w+)'", rel_call)
            if not backref_match:
                backref_match = re.search(r'backref\s*=\s*"(\w+)"', rel_call)
            if not backref_match:
                # Check for db.backref() wrapper
                backref_match = re.search(r"backref\s*=\s*db\.backref\s*\(\s*'(\w+)'", rel_call)
            if not backref_match:
                backref_match = re.search(r'backref\s*=\s*db\.backref\s*\(\s*"(\w+)"', rel_call)
            if not backref_match:
                print(f"  WARNING: Could not extract backref name in {fname}:{class_name}.{attr_name}")
                print(f"    Call: {rel_call[:200]}")
                continue
            backref_name = backref_match.group(1)
            
            # Extract extra kwargs from db.backref() wrapper (e.g., lazy='selectin')
            extra_kwargs = ''
            db_backref_match = re.search(r'db\.backref\(\s*\'?\w+\'?\s*(,\s*.+?)\)', rel_call)
            if not db_backref_match:
                db_backref_match = re.search(r'db\.backref\(\s*"\w+"\s*(,\s*.+?)\)', rel_call)
            if db_backref_match:
                extra_kwargs = db_backref_match.group(1).strip()
                if extra_kwargs.endswith(')'):
                    extra_kwargs = extra_kwargs[:-1].strip()
            
            # Extract any lazy from the relationship itself (not from backref)
            rel_lazy_match = re.search(r",\s*lazy\s*=\s*'(\w+)'", rel_call)
            if not rel_lazy_match:
                rel_lazy_match = re.search(r',\s*lazy\s*=\s*"(\w+)"', rel_call)
            
            # Extract foreign_keys if present
            rel_fk_match = re.search(r'foreign_keys\s*=\[([^\]]+)\]', rel_call)
            
            # Extract other kwargs (cascade, etc.)
            rel_other_kwargs = ''
            # Remove the relationship() function name, target model, backref, so we can extract remaining kwargs
            remaining = rel_call
            # Remove backref=... part
            remaining = re.sub(r',?\s*backref\s*=\s*(?:db\.backref\s*)?\(?[^)]*\)?\s*', ', ', remaining)
            # Remove extra whitespace
            remaining = remaining.strip().strip(',').strip()
            
            print(f"{fname}: {class_name}.{attr_name} -> {target_model}.{backref_name}")
            if extra_kwargs:
                print(f"  [backref extra kwargs: {extra_kwargs}]")
            
            backrefs.append({
                'file': fpath,
                'fname': fname,
                'class': class_name,
                'attr': attr_name,
                'target': target_model,
                'backref': backref_name,
                'extra_kwargs': extra_kwargs,
                'rel_call': rel_call,
                'rel_start': paren_start,
                'rel_end': paren_end + 1,
                'content': content,
            })

print(f"\nTotal backref relationships found: {len(backrefs)}")
print("=" * 60)

# ============================================================
# Phase 3: Apply conversions
# ============================================================

# Track changes per file
file_rewrites = {}  # filepath -> content

# First pass: modify source relationships (backref -> back_populates)
for br in backrefs:
    fpath = br['file']
    content = br['content']
    fname = br['fname']
    
    # The rel_call might have leading/trailing whitespace issues
    # Let's find the exact text in the content
    # Use the source attribute to help locate the exact relationship call
    class_body_start = br['rel_start']
    
    # Try to find the exact relationship line(s)
    # Look for attr_name = db.relationship( pattern at the right location
    search_start = max(0, class_body_start - 5)
    search_end = min(len(content), br['rel_end'] + 5)
    exact_text = content[class_body_start:br['rel_end']]
    
    old_text = br['rel_call']
    
    # Generate the new relationship call without backref
    # Remove backref=... or backref=db.backref(...)
    new_rel = old_text
    
    # Handle db.backref() wrapper first (more specific)
    new_rel = re.sub(
        r',?\s*backref\s*=\s*db\.backref\(\s*\'?' + re.escape(br['backref']) + r'\'?\s*(?:,\s*[^)]*)?\)\s*',
        f", back_populates='{br['backref']}'",
        new_rel
    )
    # Handle simple backref='name'
    new_rel = re.sub(
        r",?\s*backref\s*=\s*'\w+'\s*",
        f", back_populates='{br['backref']}'",
        new_rel
    )
    
    # If backref was the only kwarg (no leading comma), handle that
    if new_rel == old_text:
        new_rel = re.sub(
            r"backref\s*=\s*'(\w+)'\s*",
            f"back_populates='{br['backref']}'",
            new_rel
        )
    new_rel = re.sub(
        r'backref\s*=\s*"\w+"\s*',
        f'back_populates="{br["backref"]}"',
        new_rel
    )
    
    # Clean up double commas and extra whitespace
    new_rel = re.sub(r',\s*,', ',', new_rel)
    new_rel = re.sub(r'\(\s*,', '(', new_rel)
    
    # Ensure there's no comma between the model string and the next argument
    # (when backref was the only argument after model name)
    
    if old_text != new_rel:
        # Do the replacement in content
        old_absolute = content[class_body_start:br['rel_end']]
        if old_absolute in content:
            content = content.replace(old_absolute, new_rel, 1)
            print(f"  OK {fname}: {br['class']}.{br['attr']} -> back_populates='{br['backref']}'")
        else:
            print(f"  FAIL {fname}: Could not find exact text for replacement")
            print(f"    Looking for: {repr(old_absolute[:80])}")
    else:
        print(f"  SKIP {fname}: No change needed for {br['class']}.{br['attr']}")
    
    file_rewrites[fpath] = content

# Second pass: add reverse relationships to target models
# Group by target model
target_groups = defaultdict(list)
for br in backrefs:
    target_groups[(br['target'], br['target_file'] if hasattr(br, 'target_file') else None)].append(br)
    
    # Find target model file
    target_file = resolve_model_file(br['target'])
    if target_file is None:
        print(f"  ? Cannot find file for target model '{br['target']}' (from {br['fname']}:{br['class']}.{br['attr']})")
        continue
    br['target_file'] = target_file

# Now collect by target model
target_relationships = defaultdict(list)
for br in backrefs:
    if 'target_file' not in br or br['target_file'] is None:
        continue
    target_relationships[br['target_file']].append(br)

# For each target file, add reverse relationships
for target_file, br_list in target_relationships.items():
    # Read current content (may have been modified in first pass)
    if target_file in file_rewrites:
        content = file_rewrites[target_file]
    else:
        with open(target_file, 'r', encoding='utf-8') as f:
            content = f.read()
    
    tgt_fname = os.path.basename(target_file)
    
    for br in br_list:
        source_model = br['class']
        source_attr = br['attr']
        backref_name = br['backref']
        extra_kwargs = br['extra_kwargs']
        target_model = br['target']
        
        # Check if this reverse relationship already exists (back_populates)
        existing_pattern = rf"{re.escape(backref_name)}\s*=\s*db\.relationship\([^)]*back_populates\s*=\s*'{re.escape(source_attr)}'"
        if re.search(existing_pattern, content):
            print(f"  ~ {tgt_fname}: {target_model}.{backref_name} already has back_populates for {source_attr}")
            continue
        
        # Check if this attribute name already exists (possibly as a backref-created implicit attr)
        # We should still add it if it doesn't have a relationship definition
        attr_pattern = rf"^{re.escape(backref_name)}\s*=\s*db\.relationship\("
        if re.search(attr_pattern, content, re.MULTILINE):
            print(f"  ~ {tgt_fname}: {target_model}.{backref_name} already has a relationship defined")
            continue
        
        # Build the reverse relationship string
        lazy_options = ''
        if extra_kwargs:
            lazy_options = ', ' + extra_kwargs
        
        reverse_rel = f"{backref_name} = db.relationship('{source_model}', back_populates='{source_attr}'{lazy_options})"
        
        # Add it to the target model class
        new_content, added = add_relationship_to_model(content, target_model, reverse_rel)
        if added:
            content = new_content
            print(f"  + {tgt_fname}: Added {target_model}.{backref_name} -> {source_model}.{source_attr}")
        else:
            print(f"  FAIL {tgt_fname}: Could not add reverse rel to {target_model}")
    
    file_rewrites[target_file] = content

# ============================================================
# Phase 4: Write all modified files
# ============================================================
print("\n" + "=" * 60)
print("Writing modified files...")

written = 0
for fpath, content in file_rewrites.items():
    rel_path = os.path.relpath(fpath, MODELS_DIR)
    # Verify the content is valid Python by checking syntax issues
    # (basic sanity - counts of parentheses)
    open_parens = content.count('(') - content.count(')')
    if open_parens != 0:
        print(f"  FAIL {rel_path}: Unbalanced parentheses (diff={open_parens}) - SKIPPING")
        continue
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  OK {rel_path}")
    written += 1

print(f"\nTotal files written: {written}")
print("Done!")
