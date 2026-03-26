// AI suggestion component — generates GPT-4 reply and allows inserting into composer
import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import api from '../api/client';

export default function AISuggestion({ ticketId, onUse }) {
  const [suggestion, setSuggestion] = useState('');
  const [loading, setLoading] = useState(false);

  async function generate() {
    setLoading(true);
    setSuggestion('');
    try {
      const res = await api.post(`/ai/suggest/${ticketId}`);
      setSuggestion(res.data.suggestion);
    } catch {
      setSuggestion('Failed to generate suggestion.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <button onClick={generate} className="btn-secondary flex items-center gap-1 text-xs" disabled={loading}>
        <Sparkles size={14} /> {loading ? 'Generating...' : 'AI Suggest'}
      </button>
      {suggestion && (
        <div className="mt-2 bg-gray-50 border border-gray-200 rounded-lg p-3">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{suggestion}</p>
          <button
            onClick={() => onUse(suggestion)}
            className="mt-2 text-xs text-brand-600 hover:underline font-medium"
          >
            Use This Reply
          </button>
        </div>
      )}
    </div>
  );
}
