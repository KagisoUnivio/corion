const apiBase = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').replace(/\/$/, '');

export async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(apiBase + path, {
      method,
      signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Could not reach the trade API. Check that the local backend is running.');
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map(({ loc, msg }) => {
        const field = loc?.filter(part => part !== 'body').join('.');
        return field ? field + ': ' + msg : msg;
      }).join('\n')
      : detail;
    throw new Error(message || 'The trade API returned HTTP ' + response.status + '.');
  }
  if (data === null) throw new Error('The trade API returned an invalid response.');
  return data;
}
