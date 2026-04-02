// SLA Policies — create, edit, and delete SLA response/resolution targets
import { useState, useEffect } from 'react'
import { Shield, Plus, Pencil, Trash2, CheckCircle, AlertCircle, X } from 'lucide-react'
import { slaPoliciesApi } from '../api/client'
import clsx from 'clsx'

// ─── Constants ────────────────────────────────────────────────────────────────

const PRIORITY_BADGE = {
  urgent: 'bg-red-100 text-red-700',
  high:   'bg-orange-100 text-orange-700',
  normal: 'bg-blue-100 text-blue-700',
  low:    'bg-gray-100 text-gray-600',
}

const PRIORITY_OPTIONS = ['urgent', 'high', 'normal', 'low']

const CHANNEL_OPTIONS = ['email', 'whatsapp', 'instagram', 'manual', 'shopify']

const EMPTY_FORM = {
  name: '',
  priority: 'normal',
  first_response_hours: '',
  resolution_hours: '',
  warning_hours: '',
  applies_to_channels: ['email', 'whatsapp', 'instagram', 'manual'],
  is_active: true,
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function hoursToLabel(h) {
  if (h === null || h === undefined || h === '') return '—'
  const n = Number(h)
  if (n < 1) return `${Math.round(n * 60)}m`
  if (n % 1 === 0) return `${n}h`
  const hrs = Math.floor(n)
  const mins = Math.round((n % 1) * 60)
  return `${hrs}h ${mins}m`
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBanner({ status }) {
  if (!status) return null
  const isSuccess = status.type === 'success'
  return (
    <div className={clsx(
      'flex items-center gap-2 p-3 rounded-lg text-sm mb-4',
      isSuccess ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700',
    )}>
      {isSuccess ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
      {status.message}
    </div>
  )
}

function ChannelToggle({ selected, onChange }) {
  function toggle(ch) {
    if (selected.includes(ch)) {
      onChange(selected.filter(c => c !== ch))
    } else {
      onChange([...selected, ch])
    }
  }
  return (
    <div className="flex flex-wrap gap-2">
      {CHANNEL_OPTIONS.map(ch => (
        <button
          key={ch}
          type="button"
          onClick={() => toggle(ch)}
          className={clsx(
            'px-3 py-1 rounded-full text-xs font-medium border transition-colors',
            selected.includes(ch)
              ? 'bg-brand-600 text-white border-brand-600'
              : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400',
          )}
        >
          {ch}
        </button>
      ))}
    </div>
  )
}

// ─── Policy Form ──────────────────────────────────────────────────────────────

function PolicyForm({ initial, onSave, onCancel, saving }) {
  const [form, setForm] = useState(initial)

  function set(key, value) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const [formError, setFormError] = useState(null)

  function handleSubmit(e) {
    e.preventDefault()
    const resHours = parseFloat(form.resolution_hours) || 0
    const warnHours = form.warning_hours !== '' ? parseFloat(form.warning_hours) : null
    if (warnHours !== null && warnHours >= resHours) {
      setFormError(`Warning threshold (${warnHours}h) must be less than resolution time (${resHours}h). For 30 min warning, enter 0.5.`)
      return
    }
    setFormError(null)
    const payload = {
      ...form,
      first_response_hours: parseFloat(form.first_response_hours) || 0,
      resolution_hours:     resHours,
      warning_hours:        warnHours,
    }
    onSave(payload)
  }

  const inputCls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500'
  const labelCls = 'block text-sm font-medium text-gray-700 mb-1'

  return (
    <form onSubmit={handleSubmit} className="card p-6 space-y-4">
      <h2 className="text-base font-semibold text-gray-900">
        {initial.id ? 'Edit Policy' : 'New Policy'}
      </h2>

      {/* Name + Priority */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className={labelCls}>Policy Name <span className="text-red-500">*</span></label>
          <input
            required
            type="text"
            placeholder="e.g. High Priority"
            value={form.name}
            onChange={e => set('name', e.target.value)}
            className={inputCls}
          />
        </div>
        <div>
          <label className={labelCls}>Priority <span className="text-red-500">*</span></label>
          <select
            required
            value={form.priority}
            onChange={e => set('priority', e.target.value)}
            className={inputCls}
          >
            {PRIORITY_OPTIONS.map(p => (
              <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Time targets */}
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className={labelCls}>
            First Response (hours) <span className="text-red-500">*</span>
          </label>
          <input
            required
            type="number"
            min="0.1"
            step="0.5"
            placeholder="e.g. 1"
            value={form.first_response_hours}
            onChange={e => set('first_response_hours', e.target.value)}
            className={inputCls}
          />
          <p className="text-xs text-gray-400 mt-1">
            {hoursToLabel(form.first_response_hours)}
          </p>
        </div>
        <div>
          <label className={labelCls}>
            Resolution (hours) <span className="text-red-500">*</span>
          </label>
          <input
            required
            type="number"
            min="0.5"
            step="0.5"
            placeholder="e.g. 8"
            value={form.resolution_hours}
            onChange={e => set('resolution_hours', e.target.value)}
            className={inputCls}
          />
          <p className="text-xs text-gray-400 mt-1">
            {hoursToLabel(form.resolution_hours)}
          </p>
        </div>
        <div>
          <label className={labelCls}>Warning (hours)</label>
          <input
            type="number"
            min="0.1"
            step="0.1"
            placeholder="e.g. 0.5 = 30 min"
            value={form.warning_hours}
            onChange={e => set('warning_hours', e.target.value)}
            className={inputCls}
          />
          <p className="text-xs text-gray-400 mt-1">
            {form.warning_hours ? hoursToLabel(form.warning_hours) : `Auto → ${hoursToLabel((parseFloat(form.resolution_hours) || 0) * 0.75)}`}
          </p>
        </div>
      </div>

      {/* Channels */}
      <div>
        <label className={labelCls}>Applies to Channels</label>
        <ChannelToggle
          selected={form.applies_to_channels}
          onChange={val => set('applies_to_channels', val)}
        />
        <p className="text-xs text-gray-400 mt-1">
          Select which channels this policy covers. Tickets from unselected channels will fall back to any matching priority policy.
        </p>
      </div>

      {/* Active toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => set('is_active', !form.is_active)}
          className={clsx(
            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
            form.is_active ? 'bg-brand-600' : 'bg-gray-200',
          )}
        >
          <span className={clsx(
            'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform',
            form.is_active ? 'translate-x-4' : 'translate-x-1',
          )} />
        </button>
        <span className="text-sm text-gray-700">
          {form.is_active ? 'Active — will be assigned to new tickets' : 'Inactive — will not be assigned'}
        </span>
      </div>

      {/* Form-level validation error */}
      {formError && (
        <div className="flex items-center gap-2 p-3 rounded-lg text-sm bg-red-50 text-red-700">
          <AlertCircle size={15} />
          {formError}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? 'Saving…' : (initial.id ? 'Save Changes' : 'Create Policy')}
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}

// ─── Policy Card ─────────────────────────────────────────────────────────────

function PolicyCard({ policy, onEdit, onDelete }) {
  return (
    <div className={clsx(
      'card p-4 flex items-start gap-4 transition-opacity',
      !policy.is_active && 'opacity-50',
    )}>
      {/* Priority badge */}
      <div className="flex-shrink-0 pt-0.5">
        <span className={clsx('badge text-xs font-semibold', PRIORITY_BADGE[policy.priority] ?? 'bg-gray-100 text-gray-500')}>
          {policy.priority}
        </span>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-gray-900">{policy.name}</span>
          {!policy.is_active && (
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">Inactive</span>
          )}
        </div>

        <div className="flex flex-wrap gap-4 text-xs text-gray-500 mb-2">
          <span>
            <span className="font-medium text-gray-700">First response:</span>{' '}
            {hoursToLabel(policy.first_response_hours)}
          </span>
          <span>
            <span className="font-medium text-gray-700">Resolution:</span>{' '}
            {hoursToLabel(policy.resolution_hours)}
          </span>
          <span>
            <span className="font-medium text-gray-700">Warning at:</span>{' '}
            {hoursToLabel(policy.warning_hours || policy.resolution_hours * 0.75)}
          </span>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {(policy.applies_to_channels || []).map(ch => (
            <span key={ch} className="badge bg-gray-100 text-gray-600 text-xs">{ch}</span>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={() => onEdit(policy)}
          className="p-2 text-gray-400 hover:text-brand-600 hover:bg-brand-50 rounded-lg transition-colors"
          title="Edit"
        >
          <Pencil size={15} />
        </button>
        <button
          onClick={() => onDelete(policy)}
          className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="Delete"
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  )
}

// ─── Delete Confirmation ──────────────────────────────────────────────────────

function DeleteConfirm({ policy, onConfirm, onCancel, deleting }) {
  return (
    <div className="card p-5 border-red-200 bg-red-50">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm font-medium text-red-800">
          Delete <strong>{policy.name}</strong>?
        </p>
        <button onClick={onCancel} className="text-gray-400 hover:text-gray-600">
          <X size={15} />
        </button>
      </div>
      <p className="text-xs text-red-600 mb-4">
        Existing tickets already assigned this policy keep their current deadlines.
        New tickets will no longer be matched to this policy.
      </p>
      <div className="flex gap-2">
        <button
          onClick={onConfirm}
          disabled={deleting}
          className="px-3 py-1.5 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
        >
          {deleting ? 'Deleting…' : 'Yes, Delete'}
        </button>
        <button onClick={onCancel} className="btn-secondary text-sm py-1.5">
          Cancel
        </button>
      </div>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function SLAPoliciesPage() {
  const [policies,        setPolicies]        = useState([])
  const [loading,         setLoading]         = useState(true)
  const [status,          setStatus]          = useState(null)
  const [showForm,        setShowForm]        = useState(false)
  const [editingPolicy,   setEditingPolicy]   = useState(null)   // null = new
  const [deletingPolicy,  setDeletingPolicy]  = useState(null)
  const [saving,          setSaving]          = useState(false)
  const [deleting,        setDeleting]        = useState(false)
  const [applyingRetro,   setApplyingRetro]   = useState(false)

  // ── Load policies ──────────────────────────────────────────────────────────

  function loadPolicies() {
    setLoading(true)
    slaPoliciesApi.list()
      .then(res => setPolicies(res.data || []))
      .catch(() => setStatus({ type: 'error', message: 'Failed to load policies.' }))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadPolicies() }, [])

  // ── Create / Edit ──────────────────────────────────────────────────────────

  function openNewForm() {
    setEditingPolicy(null)
    setDeletingPolicy(null)
    setStatus(null)
    setShowForm(true)
  }

  function openEditForm(policy) {
    setEditingPolicy(policy)
    setDeletingPolicy(null)
    setStatus(null)
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditingPolicy(null)
  }

  async function handleSave(data) {
    setSaving(true)
    try {
      if (editingPolicy) {
        await slaPoliciesApi.update(editingPolicy.id, data)
        setStatus({ type: 'success', message: `"${data.name}" updated successfully.` })
      } else {
        await slaPoliciesApi.create(data)
        setStatus({ type: 'success', message: `"${data.name}" created successfully.` })
      }
      closeForm()
      loadPolicies()
    } catch (err) {
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to save policy.',
      })
    } finally {
      setSaving(false)
    }
  }

  // ── Retroactive SLA apply ──────────────────────────────────────────────────

  async function handleApplyRetroactive() {
    setApplyingRetro(true)
    setStatus(null)
    try {
      const res = await slaPoliciesApi.applyRetroactive()
      const { updated, skipped } = res.data
      setStatus({
        type: 'success',
        message: `Done! ${updated} ticket(s) updated with SLA deadlines, ${skipped} skipped (no matching policy).`,
      })
    } catch (err) {
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to apply retroactive SLA.',
      })
    } finally {
      setApplyingRetro(false)
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────────────

  function openDeleteConfirm(policy) {
    setDeletingPolicy(policy)
    setShowForm(false)
    setStatus(null)
  }

  async function handleDelete() {
    if (!deletingPolicy) return
    setDeleting(true)
    try {
      await slaPoliciesApi.delete(deletingPolicy.id)
      setStatus({ type: 'success', message: `"${deletingPolicy.name}" deleted.` })
      setDeletingPolicy(null)
      loadPolicies()
    } catch (err) {
      setStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to delete policy.',
      })
    } finally {
      setDeleting(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const formInitial = editingPolicy
    ? {
        ...editingPolicy,
        warning_hours: editingPolicy.warning_hours ?? '',
      }
    : EMPTY_FORM

  return (
    <div className="max-w-3xl space-y-5">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-50 rounded-lg flex items-center justify-center">
            <Shield size={20} className="text-brand-600" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">SLA Policies</h1>
            <p className="text-sm text-gray-500">
              Define response and resolution time targets per ticket priority
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleApplyRetroactive}
            disabled={applyingRetro}
            className="btn-secondary text-sm disabled:opacity-50"
            title="Assign SLA deadlines to existing open tickets that have none"
          >
            {applyingRetro ? 'Applying…' : 'Apply to Existing Tickets'}
          </button>
          {!showForm && (
            <button onClick={openNewForm} className="btn-primary flex items-center gap-2">
              <Plus size={16} />
              Add Policy
            </button>
          )}
        </div>
      </div>

      {/* Status banner */}
      <StatusBanner status={status} />

      {/* How it works info box */}
      {policies.length === 0 && !loading && (
        <div className="card p-4 bg-blue-50 border border-blue-200">
          <h3 className="text-sm font-semibold text-blue-900 mb-1">No policies yet</h3>
          <p className="text-sm text-blue-700">
            Create one policy per priority level (urgent, high, normal, low).
            When a ticket is created, the system matches it to a policy based on its priority and channel,
            then automatically sets response and resolution deadlines.
          </p>
        </div>
      )}

      {/* Existing policies */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-7 h-7 border-4 border-gray-200 border-t-brand-600 rounded-full animate-spin" />
        </div>
      ) : (
        <div className="space-y-3">
          {policies.map(policy => (
            <div key={policy.id}>
              <PolicyCard
                policy={policy}
                onEdit={openEditForm}
                onDelete={openDeleteConfirm}
              />
              {/* Delete confirmation inline under the card being deleted */}
              {deletingPolicy?.id === policy.id && (
                <div className="mt-2">
                  <DeleteConfirm
                    policy={deletingPolicy}
                    onConfirm={handleDelete}
                    onCancel={() => setDeletingPolicy(null)}
                    deleting={deleting}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* New / Edit form */}
      {showForm && (
        <PolicyForm
          initial={formInitial}
          onSave={handleSave}
          onCancel={closeForm}
          saving={saving}
        />
      )}

      {/* Reference table */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Recommended Defaults</h3>
        <table className="w-full text-xs text-gray-600">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-2 font-medium text-gray-500">Priority</th>
              <th className="text-left py-2 font-medium text-gray-500">First Response</th>
              <th className="text-left py-2 font-medium text-gray-500">Resolution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {[
              { p: 'Urgent', fr: '30 min', res: '4 h' },
              { p: 'High',   fr: '1 h',   res: '8 h' },
              { p: 'Normal', fr: '4 h',   res: '24 h' },
              { p: 'Low',    fr: '8 h',   res: '48 h' },
            ].map(row => (
              <tr key={row.p}>
                <td className="py-2 font-medium text-gray-700">{row.p}</td>
                <td className="py-2">{row.fr}</td>
                <td className="py-2">{row.res}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-gray-400 mt-3">
          Warning threshold defaults to 75% of the resolution time if not set manually.
        </p>
      </div>

    </div>
  )
}
