// Signup page — register a new agent account
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/client';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSignup(e) {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 4) {
      setError('Password must be at least 4 characters');
      return;
    }

    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);
      const res = await api.post('/auth/signup', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      localStorage.setItem('token', res.data.access_token);
      localStorage.setItem('agent', JSON.stringify(res.data.agent));
      navigate('/');
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="card p-8 w-full max-w-sm">
        <h1 className="text-xl font-semibold text-gray-900 mb-6">Create Account</h1>
        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Confirm Password</label>
            <input
              type="password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
              required
            />
          </div>
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Creating account...' : 'Sign Up'}
          </button>
        </form>
        <p className="text-sm text-gray-500 text-center mt-4">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-600 hover:underline font-medium">Log in</Link>
        </p>
      </div>
    </div>
  );
}
