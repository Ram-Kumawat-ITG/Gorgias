// New ticket page — form to create a ticket manually
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, X } from 'lucide-react';
import api from '../api/client';

export default function NewTicketPage() {
  const [subject, setSubject] = useState('');
  const [email, setEmail] = useState('');
  const [priority, setPriority] = useState('normal');
  const [message, setMessage] = useState('');
  const [images, setImages] = useState([]);
  const [imageInput, setImageInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  function addImage() {
    const url = imageInput.trim();
    if (url && url.startsWith('http')) {
      setImages(prev => [...prev, url]);
      setImageInput('');
    }
  }

  function removeImage(idx) {
    setImages(prev => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/tickets', {
        subject,
        customer_email: email,
        priority,
        channel: 'manual',
        initial_message: message || undefined,
        images: images.length > 0 ? images : undefined,
      });
      navigate(`/tickets/${res.data.id}`);
    } catch {
      setError('Failed to create ticket');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate(-1)} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 mb-4">
        ← Back
      </button>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">New Ticket</h1>
      <form onSubmit={handleSubmit} className="card p-6 space-y-4">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Subject</label>
          <input
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-brand-500"
            required
          />
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Customer Email</label>
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
          <label className="text-sm font-medium text-gray-700 block mb-1">Priority</label>
          <select
            value={priority}
            onChange={e => setPriority(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="low">Low</option>
            <option value="normal">Normal</option>
            <option value="high">High</option>
            <option value="urgent">Urgent</option>
          </select>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Initial Message</label>
          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={5}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
        </div>
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-1">Image Attachments</label>
          <div className="flex gap-2">
            <input
              type="url"
              value={imageInput}
              onChange={e => setImageInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addImage(); } }}
              placeholder="https://... (press Enter or click Add)"
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button type="button" onClick={addImage} className="btn-secondary flex items-center gap-1">
              <Plus size={14} /> Add
            </button>
          </div>
          {images.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {images.map((url, i) => (
                <div key={i} className="flex items-center gap-1 bg-gray-100 rounded-lg px-2 py-1 text-xs text-gray-700 max-w-xs">
                  <span className="truncate">{url}</span>
                  <button type="button" onClick={() => removeImage(i)} className="shrink-0 text-gray-400 hover:text-red-500">
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? 'Creating...' : 'Create Ticket'}
        </button>
      </form>
    </div>
  );
}
