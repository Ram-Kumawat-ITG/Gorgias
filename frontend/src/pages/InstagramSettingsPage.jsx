// Instagram integration settings — configure Meta Instagram Messenger API credentials
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Instagram, CheckCircle, AlertCircle } from 'lucide-react';

export default function InstagramSettingsPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [form, setForm] = useState({
    instagram_page_id: '',
    instagram_access_token: '',
    instagram_app_secret: '',
    instagram_verify_token: '',
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success'|'error', message }
  const navigate = useNavigate();
  const [testing, setTesting] = useState(false);

  const isValid = validateForm();

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
    const newForm = {
      instagram_page_id: merchant.instagram_page_id || '',
      instagram_access_token: merchant.instagram_access_token || '',
      instagram_app_secret: merchant.instagram_app_secret || '',
      instagram_verify_token: merchant.instagram_verify_token || '',
    };
    setForm(newForm);
    setStatus(null);
  }

function validateForm() {
    const required = ['instagram_page_id', 'instagram_access_token'];
    for (const field of required) {
      if (!form[field]) {
        return false;
      }
    }
    return true;
  }

  async function handleSave(e) {
    e.preventDefault();
    if (!selectedMerchant || !validateForm()) return;

    setSaving(true);
    setStatus(null);
    try {
      await api.patch(`/merchants/${selectedMerchant.id}`, form);
      setStatus({ type: 'success', message: '✅ Instagram configuration saved! Redirecting to Inbox...' });

      const res = await api.get('/merchants');
      const list = res.data.merchants || res.data || [];
      setMerchants(list);

      setTimeout(() => {
        navigate('/');
      }, 1500);

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
      await api.post('/webhooks/instagram/test', {
        merchant_id: selectedMerchant?.id,
      });
      setStatus({ type: 'success', message: 'Connection successful! Instagram API is reachable.' });
    } catch (err) {
      setStatus({ type: 'error', message: 'Connection test failed. Please verify your credentials.' });
    } finally {
      setTesting(false);
    }
  }

  const webhookUrl = window.location.origin.replace(/:\d+$/, '') + '/webhooks/instagram';
  const isConfigured = form.instagram_page_id && form.instagram_access_token;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-pink-100 rounded-lg flex items-center justify-center">
          <Instagram size={20} className="text-pink-600" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Instagram Integration</h1>
          <p className="text-sm text-gray-500">Connect your Instagram Business Account to receive and reply to DMs</p>
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
      <div className="card p-4 mb-6 bg-pink-50 border border-pink-200">
        <h3 className="text-sm font-medium text-pink-900 mb-2">Setup Guide</h3>
        <ol className="text-sm text-pink-800 space-y-1 list-decimal list-inside">
          <li>Go to <span className="font-medium">developers.facebook.com</span> and open your Meta App</li>
          <li>Add the <span className="font-medium">Instagram</span> product to your app</li>
          <li>Connect your Facebook Page linked to your Instagram Business Account</li>
          <li>Generate a permanent Page Access Token with <code>instagram_manage_messages</code> permission</li>
          <li>Enter your credentials below and save</li>
          <li>Configure the webhook URL in Meta's dashboard (shown below) — subscribe to <code>messages</code></li>
        </ol>
      </div>

      {/* Config form */}
      <form onSubmit={handleSave} className="card p-6 space-y-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">API Credentials</h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Facebook Page ID</label>
          <input
            type="text"
            value={form.instagram_page_id}
            onChange={e => setForm({ ...form, instagram_page_id: e.target.value })}
            placeholder="e.g. 123456789012345"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">The Facebook Page ID linked to your Instagram Business Account</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Page Access Token</label>
          <input
            type="password"
            value={form.instagram_access_token}
            onChange={e => setForm({ ...form, instagram_access_token: e.target.value })}
            placeholder="EAAxxxxxxxxxxxxxxx"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Use a permanent Page Access Token with instagram_manage_messages permission</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">App Secret</label>
          <input
            type="password"
            value={form.instagram_app_secret}
            onChange={e => setForm({ ...form, instagram_app_secret: e.target.value })}
            placeholder="Your Meta app secret"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Used to verify webhook signatures (X-Hub-Signature-256)</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Webhook Verify Token</label>
          <input
            type="text"
            value={form.instagram_verify_token}
            onChange={e => setForm({ ...form, instagram_verify_token: e.target.value })}
            placeholder="any-random-string-you-choose"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">You create this string — enter the same value in Meta's webhook config</p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button type="submit" className="btn-primary" disabled={saving || !selectedMerchant}>
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
          Enter this URL in your Meta App Dashboard under Instagram &gt; Webhooks:
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
              <span className="w-1.5 h-1.5 bg-pink-500 rounded-full"></span>
              <code>messages</code> — Receive incoming customer DMs
            </li>
          </ul>
        </div>
      </div>

      {/* 24-hour window info */}
      <div className="card p-6 mt-6">
        <h2 className="text-lg font-medium text-gray-900 mb-2">24-Hour Messaging Window</h2>
        <p className="text-sm text-gray-600">
          Instagram Messenger has a <strong>24-hour customer service window</strong>.
          After a customer sends you a DM, you can send free-form replies for 24 hours.
          After that window expires, you can no longer send messages to that conversation
          until the customer messages you again.
        </p>
        <p className="text-sm text-gray-600 mt-2">
          The system automatically tracks this window and will warn you when it expires.
        </p>
      </div>
    </div>
  );
}
