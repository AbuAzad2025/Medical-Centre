/* Arabic digit conversion - TypeScript */
const ARABIC_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'];

function toArabicDigits(str: string): string {
  return str.replace(/\d/g, (d) => ARABIC_DIGITS[parseInt(d)]);
}

function toEnglishDigits(str: string): string {
  return str.replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)));
}

(window as any).toArabicDigits = toArabicDigits;
(window as any).toEnglishDigits = toEnglishDigits;