/* Smart select - TypeScript */
function initSmartSelect(selectId: string, options?: any): void {
  const select = document.getElementById(selectId) as HTMLSelectElement | null;
  if (!select) return;
  // Tom Select or Select2 initialization
  if (typeof (window as any).TomSelect !== 'undefined') {
    new (window as any).TomSelect(select, options || { create: false });
  } else if (typeof $ !== 'undefined' && $.fn.select2) {
    $(select).select2(options || {});
  }
}

(window as any).initSmartSelect = initSmartSelect;