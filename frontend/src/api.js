const BASE = '/api'

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}))
    throw new Error(detail.detail || `${resp.status} ${resp.statusText}`)
  }
  return resp.status === 204 ? null : resp.json()
}

export const api = {
  catalog: () => request('/cards/catalog'),
  myCards: () => request('/cards/mine'),
  addCard: (body) => request('/cards/mine', { method: 'POST', body: JSON.stringify(body) }),
  removeCard: (id) => request(`/cards/mine/${id}`, { method: 'DELETE' }),
  dashboard: () => request('/advisor/dashboard'),
  swipe: (body) => request('/advisor/swipe', { method: 'POST', body: JSON.stringify(body) }),
  transactions: () => request('/transactions?limit=50'),
  addTransaction: (body) => request('/transactions', { method: 'POST', body: JSON.stringify(body) }),
  uploadStatement: (formData) => request('/transactions/upload', { method: 'POST', body: formData }),
  correctCategory: (id, body) =>
    request(`/transactions/${id}/category`, { method: 'PATCH', body: JSON.stringify(body) }),
  redemptionAdvice: (userCardId) => request(`/redemption/advise/${userCardId}`),
  logRedemption: (body) => request('/redemption/events', { method: 'POST', body: JSON.stringify(body) }),
  recommend: (ltfOnly) => request(`/recommend/cards?ltf_only=${ltfOnly}`),
  travelSearch: (body) => request('/travel/search', { method: 'POST', body: JSON.stringify(body) }),
  fareAlerts: () => request('/travel/alerts'),
  addFareAlert: (body) => request('/travel/alerts', { method: 'POST', body: JSON.stringify(body) }),
  removeFareAlert: (id) => request(`/travel/alerts/${id}`, { method: 'DELETE' }),
  chat: (message) => request('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
  notifications: () => request('/notifications'),
}

export const CATEGORIES = [
  'retail_default', 'groceries', 'dining', 'fuel', 'utilities', 'insurance',
  'travel', 'entertainment', 'online_shopping', 'wallet_load', 'rent',
  'government', 'education',
]

export const inr = (n) =>
  '₹' + Number(n ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })
