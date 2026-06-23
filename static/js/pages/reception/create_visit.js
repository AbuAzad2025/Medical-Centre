var __M = window.__M || [];

document.addEventListener('DOMContentLoaded', function() {
    const selectedPatientId = document.getElementById('selectedPatientId');
    const selectedPatientInfo = document.getElementById('selectedPatientInfo');
    const addNewPatientBtn = document.getElementById('addNewPatientBtn');

    var prePid = __M0__;
    var preDept = __M1__;
    var preDoc = __M2__;
    var PRESELECTED_PATIENT = __M3__;
    if (PRESELECTED_PATIENT) {
        (function initPreselectedPatient(){
            selectedPatientId.value = PRESELECTED_PATIENT.id;
            selectedPatientInfo.innerHTML = `
                <strong>المريض المحدد:</strong> ${PRESELECTED_PATIENT.full_name} | 
                الهوية: ${PRESELECTED_PATIENT.national_id} | 
                الهاتف: ${PRESELECTED_PATIENT.phone}
            `;
            selectedPatientInfo.classList.remove('d-none');
            selectedPatientInfo.style.display = 'block';
        })();
    }

    // البحث الذكي — يُدار عبر smart-search.js + /api/search/patients

    // إضافة مريض جديد
    addNewPatientBtn.addEventListener('click', function() {
        window.open('/reception/patients?show_add=1', '_blank');
    });

    // تحديث الموظفين عند تغيير القسم
    const departmentSelect = document.getElementById('department_id');
    const staffSelect = document.getElementById('staff_id');
    const staffContainer = document.getElementById('staff_container');
    const testSection = document.getElementById('test_selection_section');
    const testsSelect = document.getElementById('selected_tests');

    $('#department_id').on('change', function() {
        const departmentId = this.value;
        staffSelect.innerHTML = '<option value="">جاري التحميل...</option>';

        if (departmentId) {
            fetch(`/reception/api/department-services?department_id=${departmentId}`)
                .then(r => r.json())
                .then(svc => {
                        const isLabOrRad = svc.category === 'lab' || svc.category === 'radiology';
                        
                        // دائماً إظهار اختيار الموظف (لأن المختبر والأشعة لديهم موظفين أيضاً)
                        staffContainer.style.display = '';
                        
                        // جلب الموظفين لهذا القسم (سواء كان عيادة أو مختبر أو أشعة)
                        staffSelect.innerHTML = '<option value="">جاري التحميل...</option>';
                        fetch(`/reception/api/department-staff?department_id=${departmentId}`)
                            .then(response => response.json())
                            .then(data => {
                                staffSelect.innerHTML = '<option value="">اختر الطبيب/الموظف...</option>';
                                if (data.staff && data.staff.length > 0) {
                                    data.staff.forEach(staff => {
                                        const option = document.createElement('option');
                                        option.value = staff.id;
                                        const roleAr = {'doctor':'طبيب','nurse':'ممرض','lab':'فني مختبر','radiology':'فني أشعة','technician':'فني','emergency':'طوارئ'}[staff.role] || staff.role;
                                        option.textContent = `${staff.full_name} - ${roleAr}`;
                                        staffSelect.appendChild(option);
                                    });
                                } else {
                                    staffSelect.innerHTML += '<option value="" disabled>لا يوجد موظفون في هذا القسم</option>';
                                }
                                // إعادة تهيئة Select2 للموظفين
                                if ($('#staff_id').hasClass('select2-hidden-accessible')) {
                                    $('#staff_id').select2('destroy');
                                }
                                $('#staff_id').select2({
                                    placeholder: 'ابحث أو اختر الطبيب/الموظف...',
                                    allowClear: true,
                                    dir: 'rtl',
                                    width: '100%',
                                    language: {
                                        noResults: function() { return 'لا توجد نتائج'; },
                                        searching: function() { return 'جاري البحث...'; }
                                    }
                                });
                            })
                            .catch(error => {
                                staffSelect.innerHTML = '<option value="">خطأ في التحميل</option>';
                            });

                        // تحديث label الفحوصات حسب نوع القسم
                        const testsLabel = document.getElementById('tests_section_label');
                        if (testsLabel) {
                            if (svc.category === 'lab') testsLabel.textContent = 'التحاليل المخبرية المطلوبة';
                            else if (svc.category === 'radiology') testsLabel.textContent = 'صور الأشعة المطلوبة';
                            else testsLabel.textContent = 'الخدمات المطلوبة';
                        }
                        if (isLabOrRad) {
                            testSection.style.display = 'flex';
                            document.getElementById('custom_services_section').style.display = 'block';
                            if ($('#selected_tests').hasClass('select2-hidden-accessible')) {
                                $('#selected_tests').select2('destroy');
                            }
                            testsSelect.innerHTML = '';
                            if (svc.services) {
                                svc.services.forEach(s => {
                                    const opt = document.createElement('option');
                                    opt.value = s.id;
                                    opt.textContent = `${s.name_ar} - ${s.price} ₪`;
                                    opt.dataset.basePrice = s.base_price;
                                    opt.dataset.insurancePrice = s.insurance_price ?? '';
                                    testsSelect.appendChild(opt);
                                });
                            }
                            $('#selected_tests').select2({
                                placeholder: 'اختر الفحوصات...',
                                allowClear: true,
                                dir: 'rtl',
                                width: '100%',
                                language: {
                                    noResults: function() { return 'لا توجد نتائج'; },
                                    searching: function() { return 'جاري البحث...'; }
                                }
                            });
                        } else {
                            testSection.style.display = 'none';
                            document.getElementById('custom_services_section').style.display = 'none';
                            testsSelect.innerHTML = '';
                        }
                        calculateVisitCost();
                    })
                    .catch(() => {
                        staffContainer.style.display = '';
                        testSection.style.display = 'none';
                        testsSelect.innerHTML = '';
                        calculateVisitCost();
                    });
        } else {
            staffContainer.style.display = '';
            testSection.style.display = 'none';
            testsSelect.innerHTML = '';
            staffSelect.innerHTML = '<option value="">اختر القسم أولاً</option>';
            calculateVisitCost();
        }
    });

    // تحديث التكلفة عند تغيير المعايير
    function calculateVisitCost() {
        const departmentId = departmentSelect.value;
        const staffId = staffSelect.value;
        const visitType = document.getElementById('visit_type').value;
        const taxType = document.getElementById('tax_type').value;
        const isEmergency = document.getElementById('is_emergency').checked;
        const paymentMethod = document.getElementById('payment_method').value || 'CASH';
        const selectedTestIds = Array.from(testsSelect.selectedOptions).map(o => o.value);

        // جمع الخدمات اليدوية
        const customRows = document.querySelectorAll('.custom-service-row');
        const customNames = [];
        const customPrices = [];
        customRows.forEach(row => {
            const nameInput = row.querySelector('input[name="custom_service_name"]');
            const priceInput = row.querySelector('input[name="custom_service_price"]');
            if (nameInput && nameInput.value.trim()) {
                customNames.push(nameInput.value.trim());
                customPrices.push(priceInput ? priceInput.value : '0');
            }
        });

        if (departmentId) {
            const params = new URLSearchParams({
                department_id: departmentId,
                doctor_id: staffId,
                visit_type: visitType,
                tax_type: taxType,
                is_emergency: isEmergency,
                payment_method: (paymentMethod || '').toLowerCase()
            });
            if (selectedTestIds.length > 0) {
                params.set('test_ids', selectedTestIds.join(','));
            }
            customNames.forEach((n, i) => {
                params.append('custom_service_name', n);
                params.append('custom_service_price', customPrices[i] || '0');
            });
            fetch(`/reception/api/visit-pricing?${params.toString()}`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('visitCost').value = data.cost || '0.00';
                    if (data.tests_total) {
                        document.getElementById('testsTotalPrice').value = data.tests_total || '0.00';
                    } else {
                        document.getElementById('testsTotalPrice').value = selectedTestIds.length ? sumSelectedTests(paymentMethod) : '';
                    }
                    if (data.details && data.details.breakdown) {
                        const breakdown = data.details.breakdown.map(item => `${item.item}: ${item.cost}₪`).join(' | ');
                        document.getElementById('costBreakdown').textContent = breakdown;
                    } else {
                        document.getElementById('costBreakdown').textContent = '';
                    }
                })
                .catch(() => {
                    document.getElementById('visitCost').value = '0.00';
                    document.getElementById('testsTotalPrice').value = selectedTestIds.length ? sumSelectedTests(paymentMethod) : '';
                    document.getElementById('costBreakdown').textContent = '';
                });
        }
    }

    function sumSelectedTests(paymentMethod) {
        const methodVal = typeof paymentMethod === 'string' ? paymentMethod : (paymentMethod && paymentMethod.value) || '';
        const useInsurance = methodVal === 'INSURANCE';
        let total = 0;
        Array.from(testsSelect.selectedOptions).forEach(opt => {
            const price = useInsurance && opt.dataset.insurancePrice ? parseFloat(opt.dataset.insurancePrice) : parseFloat(opt.dataset.basePrice || '0');
            if (!isNaN(price)) total += price;
        });
        return total.toFixed(2);
    }

    // إضافة مستمعي الأحداث للتكلفة
    document.getElementById('visit_type').addEventListener('change', calculateVisitCost);
    document.getElementById('tax_type').addEventListener('change', calculateVisitCost);
    document.getElementById('is_emergency').addEventListener('change', calculateVisitCost);
    $('#staff_id').on('change', calculateVisitCost);
    document.getElementById('payment_method').addEventListener('change', calculateVisitCost);
    $('#selected_tests').on('change', calculateVisitCost);

    // إدارة حقول الدفع الديناميكية
    const paymentMethod = document.getElementById('payment_method');
    const paymentFields = document.getElementById('paymentFields');
    const advancedEl = document.getElementById('advancedVisitFields');

    function ensureAdvancedOpen() {
        if (!advancedEl) return;
        if (window.bootstrap && window.bootstrap.Collapse) {
            const inst = window.bootstrap.Collapse.getOrCreateInstance(advancedEl, { toggle: false });
            inst.show();
            return;
        }
        advancedEl.classList.add('show');
    }

    paymentMethod.addEventListener('change', function() {
        const method = this.value;
        
        // إخفاء جميع الحقول
        document.getElementById('visaFields').style.display = 'none';
        document.getElementById('insuranceFields').style.display = 'none';
        document.getElementById('forceFields').style.display = 'none';
        paymentFields.style.display = 'none';

        // إظهار الحقول المناسبة
        if (method === 'CARD') {
            document.getElementById('visaFields').style.display = 'block';
            paymentFields.style.display = 'block';
            ensureAdvancedOpen();
        } else if (method === 'INSURANCE') {
            document.getElementById('insuranceFields').style.display = 'block';
            paymentFields.style.display = 'block';
            ensureAdvancedOpen();
        } else if (method === 'FORCE') {
            document.getElementById('forceFields').style.display = 'block';
            paymentFields.style.display = 'block';
            ensureAdvancedOpen();
        }

        
        
        // إعادة حساب التكلفة عند تغيير طريقة الدفع
        calculateVisitCost();
    });

    (function initPaymentUI(){
        const method = paymentMethod.value;
        const evt = new Event('change');
        paymentMethod.dispatchEvent(evt);
    })();

    document.getElementById('visitForm').addEventListener('submit', function(e) {
        const method = paymentMethod.value || 'CASH';
        const req = {
            CASH: [],
            CARD: ['card_last_digits','card_holder_name','expiry_date'],
            INSURANCE: ['insurance_provider','insurance_policy_number'],
            FORCE: ['force_payment_reason','approved_by']
        };
        const fields = req[method] || [];
        for (let i=0;i<fields.length;i++) {
            const el = document.getElementById(fields[i]);
            if (!el || !el.value) {
                e.preventDefault();
                Swal.fire({ title: 'حقول مطلوبة', text: 'يرجى إكمال حقول الدفع المطلوبة', icon: 'warning' });
                return;
            }
        }
    });

    (function initPreselectedDeptDoctor(){
        if (preDept) {
            departmentSelect.value = preDept;
            const evt = new Event('change');
            departmentSelect.dispatchEvent(evt);
            setTimeout(() => {
                if (preDoc) {
                    staffSelect.value = preDoc;
                }
                calculateVisitCost();
            }, 400);
        }
    })();

    const posBtn = document.getElementById('posChargeBtn');
    if (posBtn) {
        posBtn.addEventListener('click', function() {
            const amtEl = document.getElementById('amount_paid');
            const amount = parseFloat(amtEl.value || document.getElementById('visitCost').value || '0');
            const statusEl = document.getElementById('posStatus');
            statusEl.textContent = '';
            if (!amount || amount <= 0) {
                Swal.fire({ title: 'تنبيه', text: 'يرجى تحديد المبلغ المراد تحصيله', icon: 'warning' });
                return;
            }
            fetch('/reception/api/pos/charge', {
                method: 'POST',
                headers: { 'Accept': 'application/json' },
                body: new URLSearchParams({ amount: amount })
            })
            .then(r => r.json())
            .then(d => {
                if (d.success) {
                    if (d.card_last_digits) document.getElementById('card_last_digits').value = d.card_last_digits;
                    if (d.card_holder_name) document.getElementById('card_holder_name').value = d.card_holder_name;
                    if (typeof d.amount !== 'undefined') amtEl.value = d.amount;
                    statusEl.textContent = 'تم التحصيل: ' + (d.transaction_id || d.approval_code || 'نجاح');
                    statusEl.className = 'text-success';
                } else {
                    statusEl.textContent = 'فشل التحصيل: ' + (d.message || '');
                    statusEl.className = 'text-danger';
                    Swal.fire({ title: 'فشل التحصيل', text: d.message || '', icon: 'error' });
                }
            })
            .catch(err => {
                statusEl.textContent = 'خطأ في الاتصال بالجهاز';
                statusEl.className = 'text-danger';
                Swal.fire({ title: 'خطأ', text: 'خطأ في الاتصال بالجهاز', icon: 'error' });
            });
        });
    }
    // حفظ وطباعة الوصل
    document.getElementById('saveAndPrintBtn').addEventListener('click', function() {
        // إضافة حقل مخفي للإشارة للطباعة
        const printInput = document.createElement('input');
        printInput.type = 'hidden';
        printInput.name = 'print_receipt';
        printInput.value = 'true';
        document.getElementById('visitForm').appendChild(printInput);
        
        // إرسال النموذج
        document.getElementById('visitForm').submit();
    });

    const quickModalEl = document.getElementById('quickEmergencyModal');
    const quickBtn = document.getElementById('quickEmergencyBtn');
    const quickCreateBtn = document.getElementById('qe_create_btn');
    const quickFlag = document.getElementById('quick_emergency');
    const quickNameHidden = document.getElementById('quick_patient_name');
    const quickGenderHidden = document.getElementById('quick_gender');
    const quickAgeHidden = document.getElementById('quick_age');
    const quickReasonHidden = document.getElementById('quick_reason');

    function showQuickModal() {
        if (!quickModalEl) return;
        if (window.bootstrap && window.bootstrap.Modal) {
            const modal = window.bootstrap.Modal.getOrCreateInstance(quickModalEl);
            modal.show();
            return;
        }
        if (window.$ && window.$.fn && window.$.fn.modal) {
            window.$(quickModalEl).modal('show');
            return;
        }
        quickModalEl.classList.add('show');
        quickModalEl.style.display = 'block';
    }

    function hideQuickModal() {
        if (!quickModalEl) return;
        if (window.bootstrap && window.bootstrap.Modal) {
            const modal = window.bootstrap.Modal.getOrCreateInstance(quickModalEl);
            modal.hide();
            return;
        }
        if (window.$ && window.$.fn && window.$.fn.modal) {
            window.$(quickModalEl).modal('hide');
            return;
        }
        quickModalEl.classList.remove('show');
        quickModalEl.style.display = 'none';
    }

    if (quickBtn) {
        quickBtn.addEventListener('click', function(e) {
            e.preventDefault();
            showQuickModal();
        });
    }

    if (quickCreateBtn) {
        quickCreateBtn.addEventListener('click', function() {
            const qeName = (document.getElementById('qe_patient_name')?.value || '').trim();
            const qeGender = (document.getElementById('qe_gender')?.value || '').trim();
            const qeAge = (document.getElementById('qe_age')?.value || '').trim();
            const qeReason = (document.getElementById('qe_reason')?.value || '').trim();

            if (!selectedPatientId.value && !qeName) {
                Swal.fire({ title: 'بيانات ناقصة', text: 'يرجى إدخال اسم المريض أو معرف مؤقت', icon: 'warning' });
                return;
            }
            if (!qeReason) {
                Swal.fire({ title: 'بيانات ناقصة', text: 'يرجى إدخال سبب الدخول', icon: 'warning' });
                return;
            }

            quickFlag.value = '1';
            quickNameHidden.value = qeName;
            quickGenderHidden.value = qeGender;
            quickAgeHidden.value = qeAge;
            quickReasonHidden.value = qeReason;

            const isEmergencyChk = document.getElementById('is_emergency');
            if (isEmergencyChk) isEmergencyChk.checked = true;
            const isForceChk = document.getElementById('is_force_payment');
            if (isForceChk) isForceChk.checked = true;

            const vt = document.getElementById('visit_type');
            if (vt) vt.value = 'EMERGENCY';

            const symptomsEl = document.getElementById('symptoms');
            if (symptomsEl && !symptomsEl.value) symptomsEl.value = qeReason;

            let emergencyDeptId = '';
            Array.from(departmentSelect.options).forEach(opt => {
                const t = (opt.textContent || '').toLowerCase();
                if (t.includes('طوارئ') || t.includes('emergency')) emergencyDeptId = opt.value;
            });
            if (emergencyDeptId) {
                departmentSelect.value = emergencyDeptId;
                const evt = new Event('change');
                departmentSelect.dispatchEvent(evt);
            }

            staffContainer.style.display = 'none';
            staffSelect.value = '';

            paymentMethod.value = 'FORCE';
            const pmEvt = new Event('change');
            paymentMethod.dispatchEvent(pmEvt);

            const forceReason = document.getElementById('force_payment_reason');
            if (forceReason && (!forceReason.value || forceReason.value.length < 10)) {
                forceReason.value = 'حالة طوارئ عاجلة، سيتم المراجعة من المدير لاحقاً';
            }
            const approvedBy = document.getElementById('approved_by');
            if (approvedBy && !approvedBy.value) {
                approvedBy.value = 'في انتظار اعتماد المدير';
            }

            calculateVisitCost();
            hideQuickModal();
            document.getElementById('visitForm').submit();
        });
    }

    // إخفاء نتائج البحث — smart-search.js

    // ====== خدمات يدوية ======
    let customServiceCounter = 0;

    function addCustomServiceRow() {
        customServiceCounter++;
        const container = document.getElementById('custom_services_container');
        const row = document.createElement('div');
        row.className = 'row mb-2 custom-service-row align-items-end';
        row.id = `custom_service_row_${customServiceCounter}`;
        row.innerHTML = `
            <div class="col-md-6">
                <input type="text" class="form-control" name="custom_service_name" placeholder="اسم الخدمة / الفحص" required>
            </div>
            <div class="col-md-4">
                <div class="input-group">
                    <input type="number" class="form-control custom-service-price" name="custom_service_price" placeholder="السعر" min="0" step="0.01" value="0" onchange="calculateVisitCost()">
                    <span class="input-group-text">₪</span>
                </div>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-outline-danger btn-sm" data-action="remove-custom-service-row" data-value="${row.id}">
                    <i class="fas fa-trash"></i> <span class="btn-label">حذف</span>
                </button>
            </div>
        `;
        container.appendChild(row);
    }

    function removeCustomServiceRow(rowId) {
        const row = document.getElementById(rowId);
        if (row) {
            row.remove();
            calculateVisitCost();
        }
    }

    // إضافة مستمعات حساب التكلفة للخدمات اليدوية
    document.getElementById('custom_services_container').addEventListener('input', function(e) {
        if (e.target.classList.contains('custom-service-price')) {
            calculateVisitCost();
        }
    });
});