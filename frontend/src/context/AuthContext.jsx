import { createContext, useContext, useState, useEffect } from 'react'
import { authApi } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [agent, setAgent] = useState(() => {
    try {
      const stored = localStorage.getItem('agent')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    authApi
      .me()
      .then((res) => {
        setAgent(res.data)
        localStorage.setItem('agent', JSON.stringify(res.data))
      })
      .catch(() => {
        localStorage.removeItem('token')
        localStorage.removeItem('agent')
        setAgent(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (email, password) => {
    const res = await authApi.login(email, password)
    const { access_token, agent: agentData } = res.data
    localStorage.setItem('token', access_token)
    localStorage.setItem('agent', JSON.stringify(agentData))
    setAgent(agentData)
    return agentData
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('agent')
    setAgent(null)
  }

  return (
    <AuthContext.Provider value={{ agent, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
