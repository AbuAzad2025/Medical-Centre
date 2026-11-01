/* DataTables initialization - TypeScript */
declare const $: any;

function initDataTable(tableId: string, options?: any): void {
  const table = document.getElementById(tableId);
  if (!table) return;
  if (typeof $ !== 'undefined' && $.fn.DataTable) {
    $(table).DataTable(options || {
      responsive: true,
      pageLength: 25,
      language: {
        search: 'بحث:',
        lengthMenu: 'عرض _MENU_ سجل',
        info: 'عرض _START_ إلى _END_ من _TOTAL_ سجل',
        paginate: { first: 'الأول', last: 'الأخير', next: 'التالي', previous: 'السابق' },
      },
    });
  }
}

(window as any).initDataTable = initDataTable;