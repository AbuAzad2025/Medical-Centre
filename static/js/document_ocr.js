/**
 * Document OCR using Tesseract.js
 * Dropzone or file input for image/PDF OCR
 */
(function() {
  'use strict';

  function initOCR() {
    const ocrContainers = document.querySelectorAll('[data-ocr]');
    ocrContainers.forEach(function(container) {
      const fileInput = container.querySelector('input[type="file"]');
      const resultArea = container.querySelector('[data-ocr-result]');
      const progressArea = container.querySelector('[data-ocr-progress]');
      if (!fileInput || !resultArea) return;

      fileInput.addEventListener('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;

        if (typeof Tesseract === 'undefined') {
          resultArea.innerHTML = '<div class="alert alert-warning">مكتبة Tesseract.js غير محمّلة. أضف: &lt;script src="https://cdn.jsdelivr.net/npm/tesseract.js@4/dist/tesseract.min.js"&gt;&lt;/script&gt;</div>';
          return;
        }

        try {
          resultArea.textContent = '';
          if (progressArea) progressArea.textContent = 'جاري التعرف... 0%';

          const lang = document.documentElement.lang === 'ar' ? 'ara' : 'eng';
          const { data: { text } } = await Tesseract.recognize(
            file,
            lang,
            {
              logger: function(m) {
                if (progressArea && m.status === 'recognizing text') {
                  progressArea.textContent = 'جاري التعرف... ' + Math.round(m.progress * 100) + '%';
                }
              }
            }
          );

          resultArea.textContent = text;
          if (progressArea) progressArea.textContent = 'اكتمل!';
        } catch (err) {
          console.error('OCR error', err);
          if (progressArea) progressArea.textContent = 'خطأ: ' + err.message;
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOCR);
  } else {
    initOCR();
  }
})();
