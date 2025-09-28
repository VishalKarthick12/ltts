'use client'

import { useEffect, useState, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { Loader2, ShieldCheck } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { useCurrentUser } from '@/hooks/useApi'
import { getAuthToken } from '@/lib/api'

interface ProtectedRouteProps {
  children: ReactNode
  requireAuth?: boolean
  redirectTo?: string
}

export default function ProtectedRoute({ 
  children, 
  requireAuth = true, 
  redirectTo = '/login'
}: ProtectedRouteProps) {
  const router = useRouter()
  const [isChecking, setIsChecking] = useState(true)
  const [shouldRedirect, setShouldRedirect] = useState(false)
  
  const { data: user, isLoading: userLoading, error: userError } = useCurrentUser()

  // Check authentication status
  useEffect(() => {
    const checkAuth = () => {
      const token = getAuthToken()
      
      if (!requireAuth) {
        setIsChecking(false)
        return
      }

      if (!token) {
        setShouldRedirect(true)
        return
      }

      // Wait for user query to complete
      if (!userLoading) {
        if (userError || !user) {
          setShouldRedirect(true)
          return
        }
        
        if (user) {
          setIsChecking(false)
          return
        }
      }
    }

    checkAuth()
  }, [user, userLoading, userError, requireAuth])

  // Handle redirect in useEffect
  useEffect(() => {
    if (shouldRedirect && !isChecking) {
      router.push(redirectTo)
    }
  }, [shouldRedirect, isChecking, router, redirectTo])

  // Show loading state
  if (isChecking || userLoading || shouldRedirect) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <Card className="w-full max-w-md shadow-xl border-0 bg-white/80 backdrop-blur-sm">
          <CardContent className="py-12 px-8 text-center">
            <div className="space-y-6">
              <div className="mx-auto w-16 h-16 bg-gradient-to-r from-blue-600 to-cyan-600 rounded-full flex items-center justify-center">
                <ShieldCheck className="h-8 w-8 text-white" />
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center justify-center space-x-2">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                  <span className="text-lg font-medium text-gray-900">
                    {shouldRedirect ? 'Redirecting...' : 'Checking authentication...'}
                  </span>
                </div>
                <p className="text-sm text-gray-600">
                  {shouldRedirect 
                    ? 'Please wait while we redirect you'
                    : 'Verifying your credentials'
                  }
                </p>
              </div>
              
              <div className="w-full bg-gray-200 rounded-full h-1">
                <div className="h-1 bg-gradient-to-r from-blue-600 to-cyan-600 rounded-full animate-pulse w-3/4" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // User is authenticated, render children
  return <>{children}</>
}
