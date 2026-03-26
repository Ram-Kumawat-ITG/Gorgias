// Customer sidebar — shows customer info, orders, and activity history
import { useState, useEffect } from 'react';
import { ExternalLink } from 'lucide-react';
import api from '../api/client';
import CustomerHistory from './CustomerHistory';
import clsx from 'clsx';

const FULFILLMENT_COLORS = {
  fulfilled: 'bg-green-100 text-green-700',
  partial: 'bg-yellow-100 text-yellow-700',
  null: 'bg-gray-100 text-gray-600',
};

export default function CustomerSidebar({ ticket }) {
  const [customer, setCustomer] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!ticket?.customer_email) return;
    api.get(`/customers/${encodeURIComponent(ticket.customer_email)}/profile`)
      .then(res => {
        setCustomer(res.data.customer);
        setOrders(res.data.orders || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [ticket?.customer_email]);

  if (loading) return <div className="card p-4 text-sm text-gray-400">Loading customer...</div>;
  if (!customer) return <div className="card p-4 text-sm text-gray-400">No customer data</div>;

  return (
    <div className="space-y-4">
      {/* Customer info */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Customer</h3>
        <div className="space-y-1.5 text-sm">
          <p className="font-medium text-gray-800">
            {customer.first_name} {customer.last_name}
          </p>
          <p className="text-gray-500">{customer.email}</p>
          <div className="flex items-center justify-between pt-2 border-t border-gray-100 mt-2">
            <span className="text-gray-500">Total Spent</span>
            <span className="font-medium">${customer.total_spent}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Orders</span>
            <span className="font-medium">{customer.orders_count}</span>
          </div>
          {customer.shopify_customer_id && (
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Shopify ID</span>
              <span className="text-xs text-gray-400">{customer.shopify_customer_id}</span>
            </div>
          )}
        </div>
      </div>

      {/* Orders */}
      {orders.length > 0 && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Recent Orders</h3>
          <div className="space-y-2">
            {orders.slice(0, 5).map((o, i) => (
              <div key={i} className="text-xs border-b border-gray-50 pb-2 last:border-0">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-800">#{o.order_number}</span>
                  <span className={clsx('badge', FULFILLMENT_COLORS[o.fulfillment_status] || FULFILLMENT_COLORS.null)}>
                    {o.fulfillment_status || 'unfulfilled'}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <span className="text-gray-500">{o.financial_status}</span>
                  <span className="font-medium">${o.total_price} {o.currency}</span>
                </div>
                {o.tracking_url && (
                  <a href={o.tracking_url} target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-brand-600 hover:underline mt-0.5">
                    Track <ExternalLink size={10} />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity history */}
      <CustomerHistory customerEmail={ticket.customer_email} />
    </div>
  );
}
