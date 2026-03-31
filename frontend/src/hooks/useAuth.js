// Auth hook — reads agent from localStorage, provides logout
export default function useAuth() {
  const token = localStorage.getItem('token');
  const agentRaw = localStorage.getItem('agent');
  const agent = agentRaw ? JSON.parse(agentRaw) : null;
  const isLoggedIn = !!token && !!agent;

  function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('agent');
  }

  return { agent, isLoggedIn, logout };
}
