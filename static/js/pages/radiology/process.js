var __M = window.__M || [];
(function () {
            const testNameEl = document.getElementById('test_name');
            const bodyPartEl = document.getElementById('body_part');
            const templateEl = document.getElementById('report_template');
            const applyBtn = document.getElementById('apply_template_btn');
            const manageBtn = document.getElementById('manage_templates_btn');
            const findingsEl = document.getElementById('findings');
            const impressionEl = document.getElementById('results');
            const recommendationsEl = document.getElementById('recommendations');

            if (!templateEl || !applyBtn || !findingsEl || !impressionEl || !recommendationsEl) {
                return;
            }

            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
            const templatesModalEl = document.getElementById('radiologyTemplatesModal');
            const macrosModalEl = document.getElementById('radiologyMacrosModal');
            const tplForm = document.getElementById('radiologyTemplateForm');
            const tplTableBody = document.getElementById('tpl_table_body');
            const tplRefreshBtn = document.getElementById('tpl_refresh_btn');
            const tplResetBtn = document.getElementById('tpl_reset_btn');
            const tplIdEl = document.getElementById('tpl_id');
            const tplNameEl = document.getElementById('tpl_name');
            const tplModalityEl = document.getElementById('tpl_modality');
            const tplFindingsEl = document.getElementById('tpl_findings');
            const tplImpressionEl = document.getElementById('tpl_impression');
            const tplRecommendationsEl = document.getElementById('tpl_recommendations');
            const tplActiveEl = document.getElementById('tpl_active');

            let templatesCache = [];
            let macrosCache = [];

            const macroSelectEl = document.getElementById('report_macro');
            const macroTargetEl = document.getElementById('macro_target');
            const applyMacroBtn = document.getElementById('apply_macro_btn');
            const macroForm = document.getElementById('radiologyMacroForm');
            const macroTableBody = document.getElementById('macro_table_body');
            const macroRefreshBtn = document.getElementById('macro_refresh_btn');
            const macroResetBtn = document.getElementById('macro_reset_btn');
            const macroIdEl = document.getElementById('macro_id');
            const macroNameEl = document.getElementById('macro_name');
            const macroTextEl = document.getElementById('macro_text');
            const macroActiveEl = document.getElementById('macro_active');
            const aiAssistBtn = document.getElementById('ai_assist_btn');
            const aiAssistOutput = document.getElementById('ai_assist_output');
            const pacsUrlEl = document.getElementById('pacs_url');
            const studyUidEl = document.getElementById('study_uid');

            function guessTemplateFromTestName() {
                const tn = (testNameEl && testNameEl.value ? String(testNameEl.value) : '').toLowerCase();
                if (tn.includes('ct')) return 'CT';
                if (tn.includes('mri')) return 'MRI';
                if (tn.includes('x-ray') || tn.includes('xray')) return 'XRAY';
                if (tn.includes('ultra') || tn.includes('u/s') || tn.includes('us')) return 'US';
                return '';
            }

            function getBodyPart() {
                const v = bodyPartEl && bodyPartEl.value ? String(bodyPartEl.value).trim() : '';
                return v || '________';
            }

            async function runAiAssist() {
                if (!aiAssistBtn || !aiAssistOutput) return;
                aiAssistBtn.disabled = true;
                aiAssistOutput.textContent = 'جاري التحليل...';
                const payload = {
                    modality: guessTemplateFromTestName(),
                    body_part: getBodyPart(),
                    impression: impressionEl ? impressionEl.value : '',
                    study_uid: studyUidEl ? studyUidEl.value : '',
                    pacs_url: pacsUrlEl ? pacsUrlEl.value : ''
                };
                try {
                    const r = await fetch(__M0__, {
                        method: 'POST',
                        headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                        body: JSON.stringify(payload)
                    });
                    const data = await r.json().catch(() => ({}));
                    aiAssistBtn.disabled = false;
                    if (!data || !data.success || !data.data) {
                        aiAssistOutput.textContent = 'تعذر الحصول على توصيات حالياً';
                        return;
                    }
                    const suggestions = data.data.suggestions || [];
                    const disclaimer = data.data.disclaimer || '';
                    const ref = data.data.external_ref || '';
                    const lines = [];
                    for (const s of suggestions) {
                        lines.push('• ' + s);
                    }
                    if (disclaimer) {
                        lines.push(disclaimer);
                    }
                    if (ref) {
                        lines.push('مرجع: ' + ref);
                    }
                    aiAssistOutput.textContent = lines.join('\n');
                } catch (err) {
                    console.error('خطأ في الاتصال:', err);
                }
            }

            async function fetchTemplates() {
                try {
                    const r = await fetch(__M1__, { method: 'GET' });
                    const data = await r.json().catch(() => ({}));
                    const arr = data && data.templates ? data.templates : [];
                    templatesCache = Array.isArray(arr) ? arr : [];
                    return templatesCache;
                } catch (err) {
                    console.error('خطأ في الاتصال:', err);
                }
            }

            async function fetchMacros() {
                try {
                    const r = await fetch(__M2__, { method: 'GET' });
                    const data = await r.json().catch(() => ({}));
                    const arr = data && data.macros ? data.macros : [];
                    macrosCache = Array.isArray(arr) ? arr : [];
                    return macrosCache;
                } catch (err) {
                    console.error('خطأ في الاتصال:', err);
                }
            }

            if (aiAssistBtn) {
                aiAssistBtn.addEventListener('click', runAiAssist);
            }

            function fillTemplateSelect(templates) {
                const selected = templateEl.value || '';
                templateEl.innerHTML = '<option value="">بدون</option>';
                const active = templates.filter(t => t && t.is_active !== false);
                active.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t.id;
                    opt.textContent = `${(t.modality || '').toUpperCase()} - ${t.name || ''}`.trim();
                    templateEl.appendChild(opt);
                });
                if (selected) templateEl.value = selected;
            }

            function fillMacroSelect(macros) {
                if (!macroSelectEl) return;
                const selected = macroSelectEl.value || '';
                macroSelectEl.innerHTML = '<option value="">اختر</option>';
                const active = macros.filter(m => m && m.is_active !== false);
                active.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m.id;
                    opt.textContent = m.name || '';
                    macroSelectEl.appendChild(opt);
                });
                if (selected) macroSelectEl.value = selected;
            }

            function replaceBodyPart(text, bodyPart) {
                const src = String(text || '');
                return src.split(__M3__).join(bodyPart);
            }

            function applyTemplateById(templateId) {
                const tpl = templatesCache.find(t => t && t.id === templateId);
                if (!tpl) return;
                const bp = getBodyPart();

                const hasAnyContent = Boolean(
                    (findingsEl.value && findingsEl.value.trim()) ||
                    (impressionEl.value && impressionEl.value.trim()) ||
                    (recommendationsEl.value && recommendationsEl.value.trim())
                );

                if (hasAnyContent) {
                    const ok = window.confirm('سيتم استبدال النص الحالي بالقالب المختار. متابعة؟');
                    if (!ok) return;
                }

                findingsEl.value = replaceBodyPart(tpl.findings, bp);
                impressionEl.value = replaceBodyPart(tpl.impression, bp);
                recommendationsEl.value = replaceBodyPart(tpl.recommendations, bp);
            }

            function syncTemplateSelectionByModality() {
                if (templateEl.value) return;
                const guessed = guessTemplateFromTestName();
                if (!guessed) return;
                const match = templatesCache.find(t => t && (t.modality || '').toUpperCase() === guessed && t.is_active !== false);
                if (match) templateEl.value = match.id;
            }

            function resetTemplateForm() {
                tplIdEl.value = '';
                tplNameEl.value = '';
                tplModalityEl.value = guessTemplateFromTestName() || 'XRAY';
                tplFindingsEl.value = '';
                tplImpressionEl.value = '';
                tplRecommendationsEl.value = '';
                tplActiveEl.checked = true;
            }

            function renderTemplatesTable() {
                if (!tplTableBody) return;
                tplTableBody.innerHTML = '';
                templatesCache.forEach(t => {
                    if (!t || !t.id) return;
                    const tr = document.createElement('tr');
                    const active = t.is_active !== false;
                    tr.innerHTML = `
                        <td>${String(t.name || '')}</td>
                        <td><span class="badge bg-light text-dark">${String((t.modality || '').toUpperCase())}</span></td>
                        <td>${active ? '<span class="badge bg-success">نعم</span>' : '<span class="badge bg-secondary">لا</span>'}</td>
                        <td class="text-end">
                            <button type="button" class="btn btn-sm btn-outline-primary me-1" data-action="edit" data-id="${t.id}">تعديل</button>
                            <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${t.id}">حذف</button>
                        </td>
                    `;
                    tplTableBody.appendChild(tr);
                });
            }

            function resetMacroForm() {
                if (!macroIdEl) return;
                macroIdEl.value = '';
                macroNameEl.value = '';
                macroTextEl.value = '';
                macroActiveEl.checked = true;
            }

            function renderMacrosTable() {
                if (!macroTableBody) return;
                macroTableBody.innerHTML = '';
                macrosCache.forEach(m => {
                    if (!m || !m.id) return;
                    const tr = document.createElement('tr');
                    const active = m.is_active !== false;
                    tr.innerHTML = `
                        <td>${String(m.name || '')}</td>
                        <td>${active ? '<span class="badge bg-success">نعم</span>' : '<span class="badge bg-secondary">لا</span>'}</td>
                        <td class="text-end">
                            <button type="button" class="btn btn-sm btn-outline-primary me-1" data-action="edit" data-id="${m.id}">تعديل</button>
                            <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${m.id}">حذف</button>
                        </td>
                    `;
                    macroTableBody.appendChild(tr);
                });
            }

            async function refreshTemplatesUI() {
                await fetchTemplates();
                fillTemplateSelect(templatesCache);
                renderTemplatesTable();
                syncTemplateSelectionByModality();
            }

            async function refreshMacrosUI() {
                await fetchMacros();
                fillMacroSelect(macrosCache);
                renderMacrosTable();
            }

            refreshTemplatesUI();
            refreshMacrosUI();
            if (testNameEl) {
                testNameEl.addEventListener('change', function () {
                    templateEl.value = '';
                    syncTemplateSelectionByModality();
                });
            }

            applyBtn.addEventListener('click', function () {
                const id = templateEl.value;
                if (!id) {
                    if (window.notify) window.notify.warning('اختر قالباً أولاً.');
                    return;
                }
                applyTemplateById(id);
            });

            if (templatesModalEl) {
                templatesModalEl.addEventListener('show.bs.modal', function () {
                    resetTemplateForm();
                    refreshTemplatesUI();
                });
            }

            if (macrosModalEl) {
                macrosModalEl.addEventListener('show.bs.modal', function () {
                    resetMacroForm();
                    refreshMacrosUI();
                });
            }
            if (macroRefreshBtn) {
                macroRefreshBtn.addEventListener('click', function () {
                    refreshMacrosUI();
                });
            }
            if (macroResetBtn) {
                macroResetBtn.addEventListener('click', function () {
                    resetMacroForm();
                });
            }
            if (applyMacroBtn) {
                applyMacroBtn.addEventListener('click', function () {
                    const id = macroSelectEl ? macroSelectEl.value : '';
                    if (!id) return;
                    const m = macrosCache.find(x => x && x.id === id);
                    if (!m) return;
                    const target = macroTargetEl ? macroTargetEl.value : 'findings';
                    const el = document.getElementById(target);
                    if (!el) return;
                    const current = el.value ? String(el.value) : '';
                    const insert = String(m.text || '');
                    el.value = current ? (current + "\n" + insert) : insert;
                });
            }

            if (macroForm) {
                macroForm.addEventListener('submit', async function (e) {
                    e.preventDefault();
                    const payload = {
                        id: macroIdEl.value || undefined,
                        name: macroNameEl.value || '',
                        text: macroTextEl.value || '',
                        is_active: macroActiveEl.checked
                    };
                    try {
                        const r = await fetch(__M4__, {
                            method: 'POST',
                            headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                            body: JSON.stringify(payload)
                        });
                        if (!r.ok) {
                            if (window.notify) window.notify.error('تعذّر حفظ الماكرو. حاول مرة أخرى.');
                            return;
                        }
                        resetMacroForm();
                        await refreshMacrosUI();
                    } catch (err) {
                        console.error('خطأ في الاتصال:', err);
                    }
                });
            }
            if (macroTableBody) {
                macroTableBody.addEventListener('click', async function (e) {
                    const btn = e.target && e.target.closest ? e.target.closest('button[data-action]') : null;
                    if (!btn) return;
                    const action = btn.getAttribute('data-action');
                    const id = btn.getAttribute('data-id');
                    const m = macrosCache.find(x => x && x.id === id);
                    if (!m) return;
                    if (action === 'edit') {
                        macroIdEl.value = m.id;
                        macroNameEl.value = m.name || '';
                        macroTextEl.value = m.text || '';
                        macroActiveEl.checked = m.is_active !== false;
                    } else if (action === 'delete') {
                        const ok = window.confirm('حذف الماكرو؟');
                        if (!ok) return;
                        try {
                            const r = await fetch(`__M5__`.replace('__M__', encodeURIComponent(id)), {
                                method: 'POST',
                                headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {}
                            });
                            if (!r.ok) {
                                if (window.notify) window.notify.error('تعذّر الحذف. حاول مرة أخرى.');
                                return;
                            }
                            await refreshMacrosUI();
                        } catch (err) {
                            console.error('خطأ في الاتصال:', err);
                        }
                    }
                });
            }
            if (tplRefreshBtn) {
                tplRefreshBtn.addEventListener('click', function () {
                    refreshTemplatesUI();
                });
            }
            if (tplResetBtn) {
                tplResetBtn.addEventListener('click', function () {
                    resetTemplateForm();
                });
            }
            if (tplTableBody) {
                tplTableBody.addEventListener('click', async function (e) {
                    const btn = e.target && e.target.closest ? e.target.closest('button[data-action]') : null;
                    if (!btn) return;
                    const action = btn.getAttribute('data-action');
                    const id = btn.getAttribute('data-id');
                    const tpl = templatesCache.find(t => t && t.id === id);
                    if (!tpl) return;
                    if (action === 'edit') {
                        tplIdEl.value = tpl.id;
                        tplNameEl.value = tpl.name || '';
                        tplModalityEl.value = (tpl.modality || 'XRAY').toUpperCase();
                        tplFindingsEl.value = tpl.findings || '';
                        tplImpressionEl.value = tpl.impression || '';
                        tplRecommendationsEl.value = tpl.recommendations || '';
                        tplActiveEl.checked = tpl.is_active !== false;
                    } else if (action === 'delete') {
                        const ok = window.confirm('حذف القالب؟');
                        if (!ok) return;
                        try {
                            const r = await fetch(`__M6__`.replace('__TPL__', encodeURIComponent(id)), {
                                method: 'POST',
                                headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {}
                            });
                            if (!r.ok) {
                                if (window.notify) window.notify.error('تعذّر الحذف. حاول مرة أخرى.');
                                return;
                            }
                            await refreshTemplatesUI();
                        } catch (err) {
                            console.error('خطأ في الاتصال:', err);
                        }
                    }
                });
            }
            if (tplForm) {
                tplForm.addEventListener('submit', async function (e) {
                    e.preventDefault();
                    const payload = {
                        id: tplIdEl.value || undefined,
                        name: tplNameEl.value || '',
                        modality: tplModalityEl.value || 'XRAY',
                        findings: tplFindingsEl.value || '',
                        impression: tplImpressionEl.value || '',
                        recommendations: tplRecommendationsEl.value || '',
                        is_active: tplActiveEl.checked
                    };
                    try {
                        const r = await fetch(__M7__, {
                            method: 'POST',
                            headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                            body: JSON.stringify(payload)
                        });
                        if (!r.ok) {
                            if (window.notify) window.notify.error('تعذّر حفظ الماكرو. حاول مرة أخرى.');
                            return;
                        }
                        resetTemplateForm();
                        await refreshTemplatesUI();
                    } catch (err) {
                        console.error('خطأ في الاتصال:', err);
                    }
                });
            }
        })();
