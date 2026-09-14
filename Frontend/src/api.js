const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
const SESSION_KEY = 'ecommerce_session'

async function request(path, options = {}, canRefresh = true) {
  const session = getStoredSession()
  const isFormData = options.body instanceof FormData
  const headers = { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers }
  if (session?.tokens?.access) headers.Authorization = `Bearer ${session.tokens.access}`
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  const data = await response.json().catch(() => ({}))
  if (response.status === 401 && canRefresh && session?.tokens?.refresh && path !== '/token/refresh/') {
    try {
      const tokens = await refreshSession(session.tokens.refresh)
      const nextSession = { ...session, tokens }
      saveSession(nextSession)
      return request(path, options, false)
    } catch {
      clearSession()
    }
  }
  if (!response.ok) {
    const errors = data.errors ? Object.values(data.errors).flat().join(' ') : data.detail || data.error
    throw new Error(errors || data.message || 'The request could not be completed.')
  }
  return data
}

async function refreshSession(refresh) {
  const response = await fetch(`${API_URL}/token/refresh/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh }) })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'Session expired.')
  return { access: data.access, refresh }
}

const query = (params) => {
  const search = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '' && value != null))
  return search.toString() ? `?${search}` : ''
}

export const api = {
  login: (body) => request('/login/', { method: 'POST', body: JSON.stringify(body) }).then((data) => ({ user: data.user, tokens: data.tokens })),
  signup: (body) => request('/signup/', { method: 'POST', body: JSON.stringify(body) }),
  verifyEmail: (token) => request(`/verify-email/?token=${encodeURIComponent(token)}`),
  refresh: refreshSession,
  categories: () => request('/categories/'),
  createCategory: (name) => request('/categories/', { method: 'POST', body: JSON.stringify({ name }) }),
  products: (params = {}) => request(`/products/${query(params)}`),
  createProduct: (body) => request('/products/', { method: 'POST', body }),
  updateProduct: (id, body) => request(`/products/${id}/`, { method: 'PATCH', body }),
  search: (q) => request(`/search/?q=${encodeURIComponent(q)}`),
  cart: () => request('/cart/'),
  addToCart: (product, quantity = 1) => request('/cart/items/', { method: 'POST', body: JSON.stringify({ product, quantity }) }),
  updateCartItem: (id, quantity) => request(`/cart/items/${id}/`, { method: 'PATCH', body: JSON.stringify({ quantity }) }),
  removeCartItem: (id) => request(`/cart/items/${id}/delete/`, { method: 'DELETE' }),
  clearCart: () => request('/cart/', { method: 'DELETE' }),
  checkout: (body) => request('/orders/checkout/', { method: 'POST', body: JSON.stringify(body) }),
  orders: () => request('/orders/'),
  adminOrders: () => request('/admin/orders/'),
  order: (id) => request(`/orders/${id}/`),
  cancelOrder: (id) => request(`/orders/${id}/cancel/`, { method: 'PATCH' }),
  bankDetails: () => request('/payments/bank-details/'),
  submitPayment: (order_id, transaction_reference) => request('/payments/', { method: 'POST', body: JSON.stringify({ order_id, transaction_reference }) }),
  payment: (orderId) => request(`/payments/${orderId}/`),
}

export function getStoredSession() { try { return JSON.parse(localStorage.getItem(SESSION_KEY)) } catch { return null } }
export function saveSession(session) { localStorage.setItem(SESSION_KEY, JSON.stringify(session)) }
export function clearSession() { localStorage.removeItem(SESSION_KEY) }
