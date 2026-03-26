// Auth hook — reads agent from localStorage, provides logout
import { useNavigate } from 'react-router-dom';

export default function useAuth() {
  const navigate = useNavigate();

  const token = localStorage.getItem('token');
  const agentRaw = localStorage.getItem('agent');
  const agent = agentRaw ? JSON.parse(agentRaw) : null;
  const isLoggedIn = !!token && !!agent;

  function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('agent');
    navigate('/login');
  }

  return { agent, isLoggedIn, logout };
}
