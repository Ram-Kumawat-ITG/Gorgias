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
  getInventory: (variantIds) => api.get('/shopify/inventory', { params: { variant_ids: variantIds.join(',') } }),
  getProductVariants: (productId) => api.get(`/shopify/products/${productId}/variants`),
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
  get: (id) => api.get(`/orders/${id}`),
  list: (params) => api.get('/orders', { params }),
  listByCustomer: (customerId) => api.get(`/orders/customer/${customerId}`),
  create: (data) => api.post('/orders', data),
  cancel: (id, data) => api.post(`/orders/${id}/cancel`, data),
  refund: (id, data) => api.post(`/orders/${id}/refund`, data),
  update: (id, data) => api.patch(`/orders/${id}`, data),
  fulfill: (id, data) => api.post(`/orders/${id}/fulfill`, data),
  markPaid: (id) => api.post(`/orders/${id}/mark-paid`),
  searchProducts: (q = '', limit = 250, sinceId = '') => api.get('/orders/products/search', { params: { q, limit, ...(sinceId ? { since_id: sinceId } : {}) } }),
}

export const customersApi = {
  search: (email, limit = 1) => api.get('/customers', { params: { search: email, limit } }),
  get: (id) => api.get(`/customers/${id}`),
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
