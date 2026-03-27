// Modal that previews customer data in Shopify format before syncing
import { useState } from 'react';
import { X, Upload } from 'lucide-react';
import api from '../api/client';

export default function SyncToShopifyModal({ customer, onClose, onSuccess }) {
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');

  const shopifyPreview = {
    email: customer.email,
    first_name: customer.first_name || '',
    last_name: customer.last_name || '',
    company: customer.company || '(none)',
    address: customer.address || '(none)',
    city: customer.city || '(none)',
    state: customer.state || '(none)',
    zip: customer.zip || '(none)',
    tags: (customer.tags || []).join(', ') || '(none)',
    note: customer.notes || '(none)',
    verified_email: 'true',
    send_email_invite: 'false',
  };

  async function handleSync() {
    setSyncing(true);
    setError('');
    try {
      const res = await api.post(`/customers/${customer.id}/sync-to-shopify`);
      onSuccess(res.data.shopify_customer_id);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to sync to Shopify');
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Sync to Shopify</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="px-5 py-4">
          <p className="text-sm text-gray-500 mb-4">
            This will create a new customer in your Shopify store with the following data:
          </p>

          <div className="bg-gray-50 rounded-lg p-4 space-y-2">
            {Object.entries(shopifyPreview).map(([key, value]) => (
              <div key={key} className="flex justify-between text-sm">
                <span className="text-gray-500 font-mono text-xs">{key}</span>
                <span className="text-gray-900 font-medium text-right max-w-[60%] truncate">
                  {value || '—'}
                </span>
              </div>
            ))}
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 bg-gray-50">
          <button onClick={onClose} className="btn-secondary" disabled={syncing}>
            Cancel
          </button>
          <button onClick={handleSync} className="btn-primary flex items-center gap-2" disabled={syncing}>
            <Upload size={14} />
            {syncing ? 'Syncing...' : 'Confirm & Sync'}
          </button>
        </div>
      </div>
    </div>
  );
}
