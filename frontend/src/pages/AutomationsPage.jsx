// Automations management page — create and manage if-then rules
import { useState, useEffect } from 'react';
import { Trash2, Plus } from 'lucide-react';
import api from '../api/client';

const TRIGGER_EVENTS = ['ticket.created', 'message.received', 'sla.breached'];
const CONDITION_FIELDS = ['subject', 'status', 'priority', 'channel', 'message_body', 'tags'];
const CONDITION_OPERATORS = ['equals', 'contains', 'not_contains', 'is_empty'];
const ACTION_TYPES = ['add_tag', 'set_priority', 'assign_to', 'set_status', 'send_macro'];

export default function AutomationsPage() {
  const [rules, setRules] = useState([]);
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState('ticket.created');
  const [conditions, setConditions] = useState([{ field: 'subject', operator: 'contains', value: '' }]);
  const [actions, setActions] = useState([{ type: 'add_tag', value: '' }]);
  const [stopProcessing, setStopProcessing] = useState(false);
  const [priority, setPriority] = useState(0);
  const [loading, setLoading] = useState(true);

  async function loadRules() {
    try {
      const res = await api.get('/automations');
      setRules(res.data);
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => { loadRules(); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    try {
      await api.post('/automations', {
        name, trigger_event: trigger, conditions, actions,
        stop_processing: stopProcessing, priority, is_active: true,
      });
      setName(''); setConditions([{ field: 'subject', operator: 'contains', value: '' }]);
      setActions([{ type: 'add_tag', value: '' }]);
      await loadRules();
    } catch {}
  }

  async function deleteRule(id) {
    try { await api.delete(`/automations/${id}`); await loadRules(); } catch {}
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Automation Rules</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Create form */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-4 h-fit">
          <h2 className="text-lg font-medium">New Rule</h2>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Name</label>
            <input type="text" value={name} onChange={e => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              required />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Trigger Event</label>
            <select value={trigger} onChange={e => setTrigger(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              {TRIGGER_EVENTS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Conditions</label>
            {conditions.map((c, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <select value={c.field} onChange={e => { const u = [...conditions]; u[i].field = e.target.value; setConditions(u); }}
                  className="border border-gray-200 rounded-lg px-2 py-1 text-sm">
                  {CONDITION_FIELDS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
                <select value={c.operator} onChange={e => { const u = [...conditions]; u[i].operator = e.target.value; setConditions(u); }}
                  className="border border-gray-200 rounded-lg px-2 py-1 text-sm">
                  {CONDITION_OPERATORS.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
                <input value={c.value} onChange={e => { const u = [...conditions]; u[i].value = e.target.value; setConditions(u); }}
                  className="flex-1 border border-gray-200 rounded-lg px-2 py-1 text-sm" placeholder="Value" />
              </div>
            ))}
            <button type="button" className="text-xs text-brand-600 hover:underline"
              onClick={() => setConditions([...conditions, { field: 'subject', operator: 'contains', value: '' }])}>
              + Add condition
            </button>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">Actions</label>
            {actions.map((a, i) => (
              <div key={i} className="flex gap-2 mb-2">
                <select value={a.type} onChange={e => { const u = [...actions]; u[i].type = e.target.value; setActions(u); }}
                  className="border border-gray-200 rounded-lg px-2 py-1 text-sm">
                  {ACTION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input value={a.value} onChange={e => { const u = [...actions]; u[i].value = e.target.value; setActions(u); }}
                  className="flex-1 border border-gray-200 rounded-lg px-2 py-1 text-sm" placeholder="Value" />
              </div>
            ))}
            <button type="button" className="text-xs text-brand-600 hover:underline"
              onClick={() => setActions([...actions, { type: 'add_tag', value: '' }])}>
              + Add action
            </button>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={stopProcessing} onChange={e => setStopProcessing(e.target.checked)} />
              Stop processing after this rule
            </label>
            <div>
              <label className="text-sm text-gray-600">Priority: </label>
              <input type="number" value={priority} onChange={e => setPriority(Number(e.target.value))}
                className="w-16 border border-gray-200 rounded px-2 py-1 text-sm" />
            </div>
          </div>

          <button type="submit" className="btn-primary flex items-center gap-1">
            <Plus size={14} /> Create Rule
          </button>
        </form>

        {/* Rules list */}
        <div className="card divide-y divide-gray-100">
          {loading ? (
            <div className="p-8 text-center text-gray-400">Loading...</div>
          ) : rules.length === 0 ? (
            <div className="p-8 text-center text-gray-400">No rules yet</div>
          ) : (
            rules.map(r => (
              <div key={r.id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium text-sm text-gray-900">{r.name}</span>
                    <span className="ml-2 badge bg-purple-100 text-purple-700">{r.trigger_event}</span>
                    {!r.is_active && <span className="ml-1 badge bg-gray-100 text-gray-500">disabled</span>}
                  </div>
                  <button onClick={() => deleteRule(r.id)} className="p-1 text-gray-400 hover:text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {r.conditions?.length || 0} condition(s), {r.actions?.length || 0} action(s)
                </p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
