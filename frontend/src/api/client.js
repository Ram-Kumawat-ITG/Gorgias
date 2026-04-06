// Axios API client — attaches JWT token, handles 401 auto-redirect
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-redirect to login on 401
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('agent');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const ticketsApi = {
  list: (params) => api.get('/tickets', { params }),
  get: (id) => api.get(`/tickets/${id}`),
  messages: (id) => api.get(`/tickets/${id}/messages`),
  create: (data) => api.post('/tickets', data),
  update: (id, data) => api.patch(`/tickets/${id}`, data),
  addMessage: (id, data) => api.post(`/tickets/${id}/messages`, data),
}

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
  register: (data) => api.post('/auth/signup', data),
}

export const shopifyApi = {
  syncOrders: (limit = 50) => api.post('/shopify/sync-orders', null, { params: { limit } }),
  listOrders: (limit = 50) => api.get('/shopify/orders', { params: { limit } }),
  getInventory: (variantIds, merchantId = null) => api.get('/shopify/inventory', { params: { variant_ids: variantIds.join(','), ...(merchantId ? { merchant_id: merchantId } : {}) } }),
  getProductVariants: (productId, merchantId = null) => api.get(`/shopify/products/${productId}/variants`, { params: merchantId ? { merchant_id: merchantId } : {} }),
}

export const aiApi = {
  analyze: (data) => api.post('/ai/analyze', data),
  processTicket: (ticketId) => api.post(`/ai/process-ticket/${ticketId}`),
  approveAction: (ticketId) => api.post(`/ai/approve-action/${ticketId}`),
  rejectAction: (ticketId, body = {}) => api.post(`/ai/reject-action/${ticketId}`, body),
}

export const channelsApi = {
  list: () => api.get('/channels'),
}

export const ordersApi = {
  get: (id, merchantId = null) => api.get(`/orders/${id}`, { params: merchantId ? { merchant_id: merchantId } : {} }),
  list: (params) => api.get('/orders', { params }),
  searchByNumber: (orderNumber, merchantId = null) => api.get('/orders/search', { params: { order_number: String(orderNumber).replace(/^#/, ''), ...(merchantId ? { merchant_id: merchantId } : {}) } }),
  listByCustomer: (customerId, merchantId = null) => api.get(`/orders/customer/${customerId}`, { params: merchantId ? { merchant_id: merchantId } : {} }),
  create: (data) => api.post('/orders', data),
  cancel: (id, data) => api.post(`/orders/${id}/cancel`, data),
  refund: (id, data) => api.post(`/orders/${id}/refund`, data),
  update: (id, data) => api.patch(`/orders/${id}`, data),
  fulfill: (id, data) => api.post(`/orders/${id}/fulfill`, data),
  markPaid: (id, merchantId = null) => api.post(`/orders/${id}/mark-paid`, null, { params: merchantId ? { merchant_id: merchantId } : {} }),
  searchProducts: (q = '', limit = 250, sinceId = '') => api.get('/orders/products/search', { params: { q, limit, ...(sinceId ? { since_id: sinceId } : {}) } }),
}

export const customersApi = {
  search: (email, limit = 1, merchantId = null) => api.get('/customers', { params: { search: email, limit, ...(merchantId ? { merchant_id: merchantId } : {}) } }),
  get: (id, merchantId = null) => api.get(`/customers/${id}`, { params: merchantId ? { merchant_id: merchantId } : {} }),
  update: (id, data) => api.patch(`/customers/${id}`, data),
}

export const slaPoliciesApi = {
  list: ()           => api.get('/sla-policies'),
  get: (id)          => api.get(`/sla-policies/${id}`),
  create: (data)     => api.post('/sla-policies', data),
  update: (id, data) => api.patch(`/sla-policies/${id}`, data),
  delete: (id)       => api.delete(`/sla-policies/${id}`),
  applyRetroactive:  () => api.post('/sla-policies/apply-retroactive'),
}

export default api;
