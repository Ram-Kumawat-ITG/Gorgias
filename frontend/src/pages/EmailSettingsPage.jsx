// Email (Mailgun) integration settings — configure Mailgun credentials exactly like WhatsApp
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Mail, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react';

export default function EmailSettingsPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [form, setForm] = useState({
    support_email: '',
    mailgun_domain: '',
    mailgun_api_key: '',
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
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
      support_email: merchant.support_email || '',
      mailgun_domain: merchant.mailgun_domain || '',
      mailgun_api_key: merchant.mailgun_api_key || '',
    };
    setForm(newForm);
    setStatus(null);
  }

  function validateForm() {
    const required = ['support_email', 'mailgun_domain', 'mailgun_api_key'];
    for (const field of required) {
      if (!form[field]) {
        return false;
      }
    }
    return true;
  }

  async function handleSave(e) {
    e.preventDefault();

    if (!selectedMerchant) {
      setStatus({ type: 'error', message: 'Please select a merchant' });
      return;
    }

    if (!isValid) return;

    setSaving(true);
    setStatus(null);
    try {
      await api.patch(`/merchants/${selectedMerchant.id}`, form);
      setStatus({ type: 'success', message: '✅ Email configuration saved! Redirecting to Inbox...' });

      const res = await api.get('/merchants');
      const list = res.data.merchants || res.data || [];
      setMerchants(list);

      setTimeout(() => {
        navigate('/requests?channel=email');
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
      const res = await api.post('/channels/email/test', {
        merchant_id: selectedMerchant?.id,
      });
      setStatus({ type: 'success', message: 'Connection successful! Mailgun API is reachable.' });
    } catch (err) {
      setStatus({ type: 'error', message: 'Connection test failed. Please verify your credentials.' });
    } finally {
      setTesting(false);
    }
  }

  const webhookUrl = window.location.origin.replace(/:\d+$/, '') + '/webhooks/email/inbound';
  const isConfigured = form.support_email && form.mailgun_api_key;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
          <Mail size={20} className="text-blue-600" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Email Integration (Mailgun)</h1>
          <p className="text-sm text-gray-500">Configure Mailgun to receive customer emails in your inbox</p>
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
          <li>Create Mailgun account at <span className="font-medium">mailgun.com</span></li>
          <li>Verify your domain and add MX records</li>
          <li>Copy API Key and Domain from Mailgun dashboard</li>
          <li>Enter your credentials below and save</li>
          <li>Configure webhook URL in Mailgun (shown below)</li>
        </ol>
      </div>

      {/* Config form */}
      <form onSubmit={handleSave} className="card p-6 space-y-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">Mailgun Credentials</h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Support Email</label>
          <input
            type="email"
            value={form.support_email}
            onChange={e => setForm({ ...form, support_email: e.target.value })}
            placeholder="support@yourdomain.com"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Customer emails will be forwarded to this address by Mailgun</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Mailgun Domain</label>
          <input
            type="text"
value={form.mailgun_domain}
            onChange={e => setForm({ ...form, mailgun_domain: e.target.value })}
            placeholder="yourdomain.com"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Your verified sending domain from Mailgun dashboard</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Mailgun API Key</label>
          <input
            type="password"
            value={form.mailgun_api_key}
            onChange={e => setForm({ ...form, mailgun_api_key: e.target.value })}
            placeholder="key-xxxxxxxxxxxxxxxxxxxx"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
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
          Add this webhook URL in Mailgun Dashboard → Domains → yourdomain.com → 
          Receiving → Add Route → Forward to webhook:
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
      </div>
    </div>
  );
}

