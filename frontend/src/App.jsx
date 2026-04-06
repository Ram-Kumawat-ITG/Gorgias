// Root app component — routing
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import InboxPage from './pages/InboxPage';
import TicketDetailPage from './pages/TicketDetailPage';
import NewTicketPage from './pages/NewTicketPage';
import MacrosPage from './pages/MacrosPage';
import AutomationsPage from './pages/AutomationsPage';
import CustomersPage from './pages/CustomersPage';
import CustomerDetailPage from './pages/CustomerDetailPage';
import OrdersPage from './pages/OrdersPage';
import OrderDetailPage from './pages/OrderDetailPage';
import ReturnsPage from './pages/ReturnsPage';
import ReturnDetailPage from './pages/ReturnDetailPage';
import AnalyticsPage from './pages/AnalyticsPage';
import RequestPage from './pages/RequestPage';
import WhatsAppSettingsPage from './pages/WhatsAppSettingsPage';
// import InstagramSettingsPage from './pages/InstagramSettingsPage';
import EmailSettingsPage from './pages/EmailSettingsPage';
import SLAPage from './pages/SLAPage';
import GiftCardPage from './pages/GiftCardPage';
import SLAPoliciesPage from './pages/SLAPoliciesPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<InboxPage />} />
        <Route path="/tickets/new" element={<NewTicketPage />} />
        <Route path="/tickets/:id" element={<TicketDetailPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/customers/:id" element={<CustomerDetailPage />} />
        <Route path="/orders" element={<OrdersPage />} />
        <Route path="/orders/:id" element={<OrderDetailPage />} />
        <Route path="/returns" element={<ReturnsPage />} />
        <Route path="/returns/:id" element={<ReturnDetailPage />} />
        <Route path="/macros" element={<MacrosPage />} />
        <Route path="/automations" element={<AutomationsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/sla" element={<SLAPage />} />
        <Route path="/sla-policies" element={<SLAPoliciesPage />} />
        <Route path="/requests" element={<RequestPage />} />
        <Route path="/gift-cards" element={<GiftCardPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/whatsapp-settings" element={<WhatsAppSettingsPage />} />
        {/* <Route path="/instagram-settings" element={<InstagramSettingsPage />} /> */}
        <Route path="/email-settings" element={<EmailSettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

