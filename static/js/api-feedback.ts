/* API feedback - TypeScript */
interface ApiResponse {
  success: boolean;
  message?: string;
  data?: any;
  errors?: string[];
}

async function apiCall(url: string, method: string = 'GET', data?: any): Promise<ApiResponse> {
  try {
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': (window as any).getCsrfToken?.() || '',
      },
      body: data ? JSON.stringify(data) : undefined,
    });
    const result = await response.json();
    if (!response.ok) {
      return { success: false, message: result.message || 'Request failed', errors: result.errors };
    }
    return { success: true, data: result, message: result.message };
  } catch (error) {
    return { success: false, message: String(error) };
  }
}

(window as any).apiCall = apiCall;