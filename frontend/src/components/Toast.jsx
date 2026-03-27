// Toast notification — auto-dismissing, supports success/error/confirm types
import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, XCircle, AlertTriangle, X } from 'lucide-react';
import clsx from 'clsx';

const ICONS = {
  success: CheckCircle,
  error: XCircle,
  confirm: AlertTriangle,
};

const COLORS = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  confirm: 'bg-yellow-50 border-yellow-200 text-yellow-800',
};

export function Toast({ message, type = 'success', onClose, onConfirm, duration = 4000 }) {
  useEffect(() => {
    if (type !== 'confirm' && duration > 0) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [type, duration, onClose]);

  const Icon = ICONS[type] || ICONS.success;

  return (
    <div className={clsx(
      'flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg max-w-sm animate-slide-in',
      COLORS[type] || COLORS.success
    )}>
      <Icon size={18} className="shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{message}</p>
        {type === 'confirm' && onConfirm && (
          <div className="flex gap-2 mt-2">
            <button onClick={onConfirm}
              className="px-3 py-1 text-xs font-medium bg-red-600 text-white rounded hover:bg-red-700 transition-colors">
              Confirm Delete
            </button>
            <button onClick={onClose}
              className="px-3 py-1 text-xs font-medium bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors">
              Cancel
            </button>
          </div>
        )}
      </div>
      {type !== 'confirm' && (
        <button onClick={onClose} className="shrink-0 opacity-60 hover:opacity-100">
          <X size={14} />
        </button>
      )}
    </div>
  );
}

// Hook to manage toast state
export function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    return id;
  }, []);

  const addConfirmToast = useCallback((message, onConfirm) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type: 'confirm', onConfirm }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return { toasts, addToast, addConfirmToast, removeToast };
}

// Container to render all active toasts
export function ToastContainer({ toasts, removeToast }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {toasts.map(t => (
        <Toast
          key={t.id}
          message={t.message}
          type={t.type}
          onClose={() => removeToast(t.id)}
          onConfirm={t.onConfirm ? () => { t.onConfirm(); removeToast(t.id); } : undefined}
        />
      ))}
    </div>
  );
}
