// Left navigation sidebar — links to all sections + agent info
import { NavLink } from 'react-router-dom';
import { Inbox, Users, ShoppingBag, RotateCcw, BarChart3, Zap, Bot, Shield, LogOut } from 'lucide-react';
import useAuth from '../hooks/useAuth';
import clsx from 'clsx';

const NAV_ITEMS = [
  { to: '/', icon: Inbox, label: 'Inbox' },
  { to: '/customers', icon: Users, label: 'Customers' },
  { to: '/orders', icon: ShoppingBag, label: 'Orders' },
  { to: '/returns', icon: RotateCcw, label: 'Returns' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/macros', icon: Bot, label: 'Macros' },
  { to: '/automations', icon: Zap, label: 'Automations' },
  { to: '/sla-policies', icon: Shield, label: 'SLA Policies' },
];

export default function Sidebar() {
  const { agent, logout } = useAuth();

  return (
    <aside className="w-56 bg-white border-r border-gray-200 flex flex-col">
      <div className="px-4 py-5 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-brand-700">Helpdesk</h2>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1">
        {NAV_ITEMS.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive
                ? 'bg-brand-50 text-brand-700'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            )}
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-gray-100">
        <p className="text-sm font-medium text-gray-900 truncate">{agent?.full_name || 'Agent'}</p>
        <p className="text-xs text-gray-400 truncate">{agent?.email}</p>
        <button
          onClick={logout}
          className="mt-2 flex items-center gap-2 text-xs text-gray-500 hover:text-red-500 transition-colors"
        >
          <LogOut size={14} /> Log out
        </button>
      </div>
    </aside>
  );
}
