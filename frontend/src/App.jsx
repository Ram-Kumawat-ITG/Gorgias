// Root app component — routing with protected routes
import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
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
import InstagramSettingsPage from './pages/InstagramSettingsPage';
import TwitterSettingsPage from './pages/TwitterSettingsPage';
import EmailSettingsPage from './pages/EmailSettingsPage';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
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
        <Route path="/requests" element={<RequestPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/whatsapp-settings" element={<WhatsAppSettingsPage />} />
        <Route path="/instagram-settings" element={<InstagramSettingsPage />} />
        <Route path="/twitter-settings" element={<TwitterSettingsPage />} />
        <Route path="/email-settings" element={<EmailSettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
