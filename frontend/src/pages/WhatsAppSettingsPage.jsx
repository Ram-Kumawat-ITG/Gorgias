// WhatsApp integration settings — configure Meta WhatsApp Business API credentials
import { useState, useEffect } from 'react';
import api from '../api/client';
import { MessageSquare, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react';

export default function WhatsAppSettingsPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [form, setForm] = useState({
    whatsapp_phone_number_id: '',
    whatsapp_waba_id: '',
    whatsapp_access_token: '',
    whatsapp_verify_token: '',
    whatsapp_app_secret: '',
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success'|'error', message }
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.get('/merchants').then(res => {
      const list = res.data.merchants || res.data || [];
      setMerchants(list);
      if (list.length > 0) {
        selectMerchant(list[0]);
      }
    }).catch(() => {});
  }, []);

  function selectMerchant(merchant) {
    setSelectedMerchant(merchant);
    setForm({
      whatsapp_phone_number_id: merchant.whatsapp_phone_number_id || '',
      whatsapp_waba_id: merchant.whatsapp_waba_id || '',
      whatsapp_access_token: merchant.whatsapp_access_token || '',
      whatsapp_verify_token: merchant.whatsapp_verify_token || '',
      whatsapp_app_secret: merchant.whatsapp_app_secret || '',
    });
    setStatus(null);
  }

  async function handleSave(e) {
    e.preventDefault();
    if (!selectedMerchant) return;
    setSaving(true);
    setStatus(null);
    try {
      await api.patch(`/merchants/${selectedMerchant.id}`, form);
      setStatus({ type: 'success', message: 'WhatsApp configuration saved successfully!' });
      // Refresh merchant list
      const res = await api.get('/merchants');
      const list = res.data.merchants || res.data || [];
      setMerchants(list);
      const updated = list.find(m => m.id === selectedMerchant.id);
      if (updated) setSelectedMerchant(updated);
    } catch (err) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Failed to save configuration' });
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setStatus(null);
    try {
      // Simple test — send a test request to verify credentials
      const res = await api.post('/webhooks/whatsapp/test', {
        merchant_id: selectedMerchant?.id,
      });
      setStatus({ type: 'success', message: 'Connection successful! WhatsApp API is reachable.' });
    } catch (err) {
      setStatus({ type: 'error', message: 'Connection test failed. Please verify your credentials.' });
    } finally {
      setTesting(false);
    }
  }

  const webhookUrl = window.location.origin.replace(/:\d+$/, '') + '/webhooks/whatsapp';
  const isConfigured = form.whatsapp_phone_number_id && form.whatsapp_access_token;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
          <MessageSquare size={20} className="text-green-600" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">WhatsApp Integration</h1>
          <p className="text-sm text-gray-500">Connect your WhatsApp Business Account to receive and reply to messages</p>
        </div>
      </div>

      {/* Merchant selector */}
      {merchants.length > 1 && (
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">Merchant</label>
          <select
            value={selectedMerchant?.id || ''}
            onChange={e => {
              const m = merchants.find(m => m.id === e.target.value);
              if (m) selectMerchant(m);
            }}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {merchants.map(m => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Status banner */}
      {status && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-4 text-sm ${
          status.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
        }`}>
          {status.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {status.message}
        </div>
      )}

      {/* Setup guide */}
      <div className="card p-4 mb-6 bg-blue-50 border border-blue-200">
        <h3 className="text-sm font-medium text-blue-900 mb-2">Setup Guide</h3>
        <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
          <li>Create a Meta Business App at <span className="font-medium">developers.facebook.com</span></li>
          <li>Add the WhatsApp product to your app</li>
          <li>Add a phone number to your WhatsApp Business Account</li>
          <li>Generate a permanent System User Access Token</li>
          <li>Enter your credentials below and save</li>
          <li>Configure the webhook URL in Meta's dashboard (shown below)</li>
        </ol>
      </div>

      {/* Config form */}
      <form onSubmit={handleSave} className="card p-6 space-y-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">API Credentials</h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number ID</label>
          <input
            type="text"
            value={form.whatsapp_phone_number_id}
            onChange={e => setForm({ ...form, whatsapp_phone_number_id: e.target.value })}
            placeholder="e.g. 123456789012345"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Found in WhatsApp &gt; API Setup in your Meta app dashboard</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp Business Account ID (WABA ID)</label>
          <input
            type="text"
            value={form.whatsapp_waba_id}
            onChange={e => setForm({ ...form, whatsapp_waba_id: e.target.value })}
            placeholder="e.g. 987654321098765"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Access Token</label>
          <input
            type="password"
            value={form.whatsapp_access_token}
            onChange={e => setForm({ ...form, whatsapp_access_token: e.target.value })}
            placeholder="EAAxxxxxxxxxxxxxxx"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Use a permanent System User token, not the temporary test token</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">App Secret</label>
          <input
            type="password"
            value={form.whatsapp_app_secret}
            onChange={e => setForm({ ...form, whatsapp_app_secret: e.target.value })}
            placeholder="Your Meta app secret"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Used to verify webhook signatures (X-Hub-Signature-256)</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Webhook Verify Token</label>
          <input
            type="text"
            value={form.whatsapp_verify_token}
            onChange={e => setForm({ ...form, whatsapp_verify_token: e.target.value })}
            placeholder="any-random-string-you-choose"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">You create this string — enter the same value in Meta's webhook config</p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
          <button
            type="button"
            onClick={testConnection}
            className="btn-secondary"
            disabled={testing || !isConfigured}
          >
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
        </div>
      </form>

      {/* Webhook URL info */}
      <div className="card p-6 mt-6">
        <h2 className="text-lg font-medium text-gray-900 mb-2">Webhook Configuration</h2>
        <p className="text-sm text-gray-600 mb-3">
          Enter this URL in your Meta App Dashboard under WhatsApp &gt; Configuration &gt; Webhook URL:
        </p>
        <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-4 py-3">
          <code className="text-sm text-gray-800 flex-1 break-all">
            {webhookUrl}
          </code>
          <button
            onClick={() => navigator.clipboard.writeText(webhookUrl)}
            className="text-xs text-brand-600 hover:text-brand-700 whitespace-nowrap"
          >
            Copy
          </button>
        </div>
        <div className="mt-4">
          <h3 className="text-sm font-medium text-gray-700 mb-1">Webhook Subscriptions Required:</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
              <code>messages</code> — Receive incoming customer messages
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
              <code>message_template_status_update</code> — Track template approval status
            </li>
          </ul>
        </div>
      </div>

      {/* 24-hour window info */}
      <div className="card p-6 mt-6">
        <h2 className="text-lg font-medium text-gray-900 mb-2">24-Hour Messaging Window</h2>
        <p className="text-sm text-gray-600">
          WhatsApp Business API has a <strong>24-hour customer service window</strong>.
          After a customer sends you a message, you can send free-form replies for 24 hours.
          After that, you can only send pre-approved <strong>message templates</strong>.
        </p>
        <p className="text-sm text-gray-600 mt-2">
          The system automatically tracks this window and will switch to template messages when the window expires.
          Make sure you have at least one approved template in your Meta Business Manager.
        </p>
      </div>
    </div>
  );
}
