const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.detail || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }

  return payload;
}

export function fetchRepositories() {
  return request('/repositories');
}

export function indexRepository(repositoryUrl) {
  return request('/repositories/index', {
    method: 'POST',
    body: JSON.stringify({ repository_url: repositoryUrl }),
  });
}

export function queryRepository(repositoryId, query) {
  return request('/query', {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId, query }),
  });
}
