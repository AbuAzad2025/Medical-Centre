/* Form validation - TypeScript */
interface ValidationRule {
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: RegExp;
  email?: boolean;
  phone?: boolean;
}

function validateField(field: HTMLInputElement, rules: ValidationRule): string | null {
  const value = field.value.trim();
  if (rules.required && !value) return 'هذا الحقل مطلوب';
  if (rules.minLength && value.length < rules.minLength) return `الحد الأدنى ${rules.minLength} أحرف`;
  if (rules.maxLength && value.length > rules.maxLength) return `الحد الأقصى ${rules.maxLength} أحرف`;
  if (rules.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'بريد إلكتروني غير صالح';
  if (rules.phone && !/^[\d\-\+\(\)\s]+$/.test(value)) return 'رقم هاتف غير صالح';
  if (rules.pattern && !rules.pattern.test(value)) return 'تنسيق غير صالح';
  return null;
}

function validateForm(form: HTMLFormElement, rules: Record<string, ValidationRule>): boolean {
  let valid = true;
  for (const [name, rule] of Object.entries(rules)) {
    const field = form.querySelector(`[name="${name}"]`) as HTMLInputElement | null;
    if (field) {
      const error = validateField(field, rule);
      if (error) {
        field.classList.add('is-invalid');
        const feedback = field.parentElement?.querySelector('.invalid-feedback');
        if (feedback) feedback.textContent = error;
        valid = false;
      } else {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
      }
    }
  }
  return valid;
}

(window as any).validateField = validateField;
(window as any).validateForm = validateForm;