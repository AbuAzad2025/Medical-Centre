with open('templates/doctor/patient_details.html', 'r', encoding='utf-8') as f:
    content = f.read()

marker = '{% if critical_lab_results_count and critical_lab_results_count > 0 %}'

new_block = '''{% if patient_allergies and patient_allergies|length > 0 %}
    <div class="row mb-4">
        <div class="col-12">
            <div class="alert alert-danger d-flex align-items-center mb-0">
                <i class="fas fa-allergies me-2 fa-lg"></i>
                <div>
                    <strong>حساسية معروفة:</strong>
                    {% for a in patient_allergies %}
                        <span class="badge bg-light text-danger border border-danger me-1">{{ a.allergen or a.name }}</span>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    {% endif %}

    {% if critical_lab_results_count and critical_lab_results_count > 0 %}'''

if marker in content:
    content = content.replace(marker, new_block)
    with open('templates/doctor/patient_details.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK allergy alert')
else:
    print('NOT FOUND allergy')

# Add dental chart button
btn_marker = '<a href="{{ url_for(\'doctor.diagnosis\', visit_id=visit.id) }}" class="btn btn-primary">'
btn_replacement = '''<a href="{{ url_for('doctor.diagnosis', visit_id=visit.id) }}" class="btn btn-primary">
                                    <i class="fas fa-stethoscope me-1"></i>
                                    التشخيص
                                </a>
                                <a href="{{ url_for('doctor.dental_chart', patient_id=visit.patient_id) }}" class="btn btn-info">
                                    <i class="fas fa-tooth me-1"></i>
                                    خريطة الأسنان
                                </a>'''

if btn_marker in content:
    content = content.replace(
        '<a href="{{ url_for(\'doctor.diagnosis\', visit_id=visit.id) }}" class="btn btn-primary">\n                                    <i class="fas fa-stethoscope me-1"></i>\n                                    التشخيص\n                                </a>',
        btn_replacement
    )
    with open('templates/doctor/patient_details.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK dental button')
else:
    print('NOT FOUND dental button')
