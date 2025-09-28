'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { useCurrentUser } from '@/hooks/useApi'
import { getAuthToken, setAuthToken } from '@/lib/api'
import { useToast } from '@/components/ui/toast'

interface AuthContextType {
  user: any
  isLoading: boolean
  isAuthenticated: boolean
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const router = useRouter()
  const { addToast } = useToast()
  const [isInitialized, setIsInitialized] = useState(false)
  
  const { data: user, isLoading: userLoading, error: userError } = useCurrentUser()

  useEffect(() => {
    // Initialize auth state
    const token = getAuthToken()
    if (token) {
      setIsInitialized(true)
    } else {
      setIsInitialized(true)
    }
  }, [])

  useEffect(() => {
    // Handle auth errors
    if (userError && isInitialized) {
      const errorStatus = (userError as any)?.status
      if (errorStatus === 401 || errorStatus === 403) {
        addToast('Your session has expired. Please log in again.', 'error')
        logout()
      }
    }
  }, [userError, isInitialized, addToast])

  const logout = () => {
    setAuthToken(null)
    router.push('/login')
  }

  const isAuthenticated = !!user && !!getAuthToken()
  const isLoading = !isInitialized || (userLoading && !!getAuthToken())

  const value = {
    user,
    isLoading,
    isAuthenticated,
    logout,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
