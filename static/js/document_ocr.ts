/* Document OCR - TypeScript */
interface OCRResult {
  text: string;
  confidence: number;
}

async function performOCR(imageFile: File): Promise<OCRResult> {
  if (typeof (window as any).Tesseract === 'undefined') {
    throw new Error('Tesseract not loaded');
  }
  const result = await (window as any).Tesseract.recognize(imageFile, 'ara+eng');
  return {
    text: result.data.text,
    confidence: result.data.confidence,
  };
}

function initOCRUpload(inputId: string, resultId: string): void {
  const input = document.getElementById(inputId) as HTMLInputElement | null;
  const result = document.getElementById(resultId);
  if (!input || !result) return;

  input.addEventListener('change', async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    result.textContent = 'Processing...';
    try {
      const ocrResult = await performOCR(file);
      result.textContent = ocrResult.text;
    } catch (error) {
      result.textContent = 'OCR failed: ' + String(error);
    }
  });
}

(window as any).performOCR = performOCR;
(window as any).initOCRUpload = initOCRUpload;