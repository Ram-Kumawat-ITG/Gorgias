// Left navigation sidebar — links to all sections + agent info
import { Link, useLocation } from 'react-router-dom';
import {
  Inbox,
  Users,
  ShoppingBag,
  BarChart3,
  Zap,
  Bot,
  Shield,
  FileText,
  RotateCcw,
  Mail,
  Gift
} from 'lucide-react';
import clsx from 'clsx';

function WhatsAppIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
    </svg>
  );
}

// matchPrefixes: array of path prefixes that should activate this item
const NAV_ITEMS = [
  { to: '/', icon: Inbox, label: 'Inbox', matchPrefixes: ['/', '/tickets'] },
  { to: '/customers', icon: Users, label: 'Customers', matchPrefixes: ['/customers'] },
  { to: '/orders', icon: ShoppingBag, label: 'Orders', matchPrefixes: ['/orders'] },
  { to: '/analytics', icon: BarChart3, label: 'Analytics', matchPrefixes: ['/analytics'] },
  { to: '/sla', icon: Shield, label: 'SLA', matchPrefixes: ['/sla'] },
  { to: '/sla-policies', icon: Shield, label: 'SLA Policies', matchPrefixes: ['/sla-policies'] },
  { to: '/macros', icon: Bot, label: 'Macros', matchPrefixes: ['/macros'] },
  { to: '/automations', icon: Zap, label: 'Automations', matchPrefixes: ['/automations'] },
  { to: '/requests', icon: FileText, label: 'Requests', matchPrefixes: ['/requests'] },
  { to: '/returns', icon: RotateCcw, label: 'Returns', matchPrefixes: ['/returns'] },
  { to: '/gift-cards', icon: Gift, label: 'Gift Cards', matchPrefixes: ['/gift-cards'] },
  { to: '/whatsapp-settings', icon: WhatsAppIcon, label: 'WhatsApp', matchPrefixes: ['/whatsapp-settings'] },
  { to: '/email-settings', icon: Mail, label: 'Email', matchPrefixes: ['/email-settings'] },
];

export default function Sidebar() {
  const { pathname } = useLocation();

  function isActive(item) {
    return item.matchPrefixes.some(prefix => {
      if (prefix === '/') return pathname === '/';
      return pathname === prefix || pathname.startsWith(prefix + '/');
    });
  }

  return (
    <aside className="w-56 h-full bg-white border-r border-gray-200 flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-gray-100">
        <h2 className="text-lg font-semibold text-brand-700">Helpdesk</h2>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(item => (
          <Link
            key={item.to}
            to={item.to}
            className={clsx(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive(item)
                ? 'bg-brand-50 text-brand-700'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            )}
          >
            <item.icon size={18} />
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Admin info removed per request */}
    </aside>
  );
}
