// Twitter integration settings — configure Twitter / X API credentials
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { CheckCircle, AlertCircle } from 'lucide-react';

export default function TwitterSettingsPage() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [form, setForm] = useState({
    twitter_api_key: '',
    twitter_api_secret: '',
    twitter_access_token: '',
    twitter_access_token_secret: '',
    twitter_bearer_token: '',
    twitter_env_name: 'production',
    twitter_user_id: '',
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
      if (list.length > 0) selectMerchant(list[0]);
    }).catch(() => {});
  }, []);

function selectMerchant(merchant) {
    setSelectedMerchant(merchant);
    const newForm = {
      twitter_api_key: merchant.twitter_api_key || '',
      twitter_api_secret: merchant.twitter_api_secret || '',
      twitter_access_token: merchant.twitter_access_token || '',
      twitter_access_token_secret: merchant.twitter_access_token_secret || '',
      twitter_bearer_token: merchant.twitter_bearer_token || '',
      twitter_env_name: merchant.twitter_env_name || 'production',
      twitter_user_id: merchant.twitter_user_id || '',
    };
    setForm(newForm);
    setStatus(null);
  }

function validateForm() {
    const required = ['twitter_api_key', 'twitter_bearer_token', 'twitter_user_id'];
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
      setStatus({ type: 'success', message: '✅ Twitter configuration saved! Redirecting to Inbox...' });

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
      const res = await api.post('/twitter/test', {
        merchant_id: selectedMerchant?.id,
      });
      setStatus({
        type: 'success',
        message: `Connected! Account: @${res.data.username} (${res.data.name})`,
      });
    } catch (err) {
      setStatus({ type: 'error', message: err.response?.data?.detail || 'Connection test failed. Please verify your credentials.' });
    } finally {
      setTesting(false);
    }
  }

  const webhookUrl = window.location.origin.replace(/:\d+$/, '') + '/webhooks/twitter';
  const isConfigured = form.twitter_bearer_token && form.twitter_api_key;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-sky-100 rounded-lg flex items-center justify-center">
          {/* Twitter/X bird icon via SVG */}
          <svg viewBox="0 0 24 24" className="w-5 h-5 fill-sky-500" aria-hidden="true">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
          </svg>
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Twitter / X Integration</h1>
          <p className="text-sm text-gray-500">Receive and reply to DMs and @mentions from Twitter / X</p>
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
      <div className="card p-4 mb-6 bg-sky-50 border border-sky-200">
        <h3 className="text-sm font-medium text-sky-900 mb-2">Setup Guide</h3>
        <ol className="text-sm text-sky-800 space-y-1 list-decimal list-inside">
          <li>Go to <span className="font-medium">developer.twitter.com</span> and create a Project + App</li>
          <li>Enable <span className="font-medium">Read, Write and Direct Messages</span> permissions</li>
          <li>Generate an Access Token and Secret (with the correct permissions)</li>
          <li>Subscribe to the <span className="font-medium">Account Activity API</span> (requires Basic tier or above)</li>
          <li>Enter your credentials below and save</li>
          <li>Register the webhook URL in Twitter's Developer Portal (shown below)</li>
          <li>Enter your Twitter account's numeric User ID in the field below for webhook matching</li>
        </ol>
      </div>

      {/* Config form */}
      <form onSubmit={handleSave} className="card p-6 space-y-4">
        <h2 className="text-lg font-medium text-gray-900 mb-2">API Credentials</h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">API Key (Consumer Key)</label>
          <input
            type="text"
            value={form.twitter_api_key}
            onChange={e => setForm({ ...form, twitter_api_key: e.target.value })}
            placeholder="e.g. xxxxxxxxxxxxxxxxxxxxxxxxx"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Found under Keys and Tokens in your Twitter App dashboard</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">API Secret (Consumer Secret)</label>
          <input
            type="password"
            value={form.twitter_api_secret}
            onChange={e => setForm({ ...form, twitter_api_secret: e.target.value })}
            placeholder="Your API Secret"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Access Token</label>
          <input
            type="text"
            value={form.twitter_access_token}
            onChange={e => setForm({ ...form, twitter_access_token: e.target.value })}
            placeholder="e.g. 123456789-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Generate with Read, Write and DM permissions enabled</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Access Token Secret</label>
          <input
            type="password"
            value={form.twitter_access_token_secret}
            onChange={e => setForm({ ...form, twitter_access_token_secret: e.target.value })}
            placeholder="Your Access Token Secret"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Bearer Token</label>
          <input
            type="password"
            value={form.twitter_bearer_token}
            onChange={e => setForm({ ...form, twitter_bearer_token: e.target.value })}
            placeholder="AAAA..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Used for connection testing and read-only API calls</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Dev Environment Name</label>
          <input
            type="text"
            value={form.twitter_env_name}
            onChange={e => setForm({ ...form, twitter_env_name: e.target.value })}
            placeholder="production"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">The environment label you configured in the Account Activity API section</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Twitter Account User ID</label>
          <input
            type="text"
            value={form.twitter_user_id}
            onChange={e => setForm({ ...form, twitter_user_id: e.target.value })}
            placeholder="e.g. 123456789"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Numeric ID of your Twitter account — used to route incoming webhook events to the right merchant</p>
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
          Register this URL in Twitter's Developer Portal under{' '}
          <span className="font-medium">Products → Account Activity API → Webhooks</span>:
        </p>
        <div className="flex items-center gap-2 bg-gray-50 rounded-lg px-4 py-3">
          <code className="text-sm text-gray-800 flex-1 break-all">{webhookUrl}</code>
          <button
            onClick={() => navigator.clipboard.writeText(webhookUrl)}
            className="text-xs text-brand-600 hover:text-brand-700 whitespace-nowrap"
          >
            Copy
          </button>
        </div>
        <div className="mt-4">
          <h3 className="text-sm font-medium text-gray-700 mb-1">Events to subscribe to:</h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-sky-500 rounded-full"></span>
              <code>direct_message_events</code> — Receive incoming DMs
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-sky-500 rounded-full"></span>
              <code>tweet_create_events</code> — Receive @mentions
            </li>
          </ul>
        </div>
      </div>

      {/* DM vs Mention info */}
      <div className="card p-6 mt-6">
        <h2 className="text-lg font-medium text-gray-900 mb-2">DMs vs @Mentions</h2>
        <div className="space-y-2 text-sm text-gray-600">
          <p>
            <strong>Direct Messages (DMs):</strong> Private messages sent directly to your Twitter account.
            Replies are sent as DMs back to the customer. No character limit issues.
          </p>
          <p>
            <strong>@Mentions:</strong> Public tweets that tag your account. Replies are posted as
            public tweet replies and are limited to <strong>280 characters</strong>.
          </p>
          <p>
            Unlike WhatsApp, Twitter has <strong>no 24-hour messaging window</strong> —
            you can reply to a customer at any time.
          </p>
        </div>
      </div>
    </div>
  );
}
