// تهيئة DataTables (إن وُجدت) مع ترجمة عربية خفيفة
export function initDataTables() {
  const hasDT = typeof window.$ !== 'undefined' && typeof window.$.fn?.DataTable === 'function';
  if (!hasDT) return;
  const lang = {
    sEmptyTable:     "لا توجد بيانات",
    sLoadingRecords: "جارِ التحميل...",
    sProcessing:     "جارِ المعالجة...",
    sLengthMenu:     "أظهر _MENU_ سجل",
    sZeroRecords:    "لم يُعثر على سجلات",
    sInfo:           "إظهار _START_ إلى _END_ من أصل _TOTAL_",
    sInfoEmpty:      "إظهار 0 إلى 0 من أصل 0",
    sInfoFiltered:   "(مرشّحة من مجموع _MAX_)",
    sSearch:         "بحث:",
    oPaginate: {
      sFirst:    "الأول",
      sLast:     "الأخير",
      sNext:     "التالي",
      sPrevious: "السابق"
    }
  };
  document.querySelectorAll('table[data-dt="1"]').forEach(tbl => {
    window.$(tbl).DataTable({ language: lang, pageLength: 25, order: [] });
  });
}
