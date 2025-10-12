// تحويل الأرقام العربية إلى لاتينية داخل الحقول النصية والعرض
const map = {'٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9'};
export function normalizeArabicDigits(root) {
  if (!root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const toFix = [];
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (/[٠-٩]/.test(n.nodeValue)) toFix.push(n);
  }
  for (const n of toFix) {
    n.nodeValue = n.nodeValue.replace(/[٠-٩]/g, d => map[d]);
  }
  // حقول الإدخال
  document.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(inp => {
    inp.addEventListener('input', () => {
      inp.value = inp.value.replace(/[٠-٩]/g, d => map[d]);
    });
  });
}
