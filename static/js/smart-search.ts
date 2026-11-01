/* Smart search - TypeScript */
interface SearchResult {
  id: number;
  text: string;
  type: string;
}

function initSmartSearch(inputId: string, resultsId: string, searchUrl: string): void {
  const input = document.getElementById(inputId) as HTMLInputElement | null;
  const results = document.getElementById(resultsId);
  if (!input || !results) return;

  let debounceTimer: ReturnType<typeof setTimeout>;

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const query = input.value.trim();
    if (query.length < 2) {
      results.innerHTML = '';
      results.style.display = 'none';
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`);
        if (response.ok) {
          const data = await response.json();
          results.innerHTML = (data.results || []).map((r: SearchResult) =>
            `<div class="search-result" data-id="${r.id}" data-type="${r.type}">${r.text}</div>`
          ).join('');
          results.style.display = 'block';
        }
      } catch {
        // Silently fail
      }
    }, 300);
  });
}

(window as any).initSmartSearch = initSmartSearch;