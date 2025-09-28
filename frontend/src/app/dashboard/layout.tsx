'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useCurrentUser } from '@/hooks/useApi'
import { getAuthToken } from '@/lib/api'
import { Loader2 } from 'lucide-react'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const [isAuthorizing, setIsAuthorizing] = useState(true)
  const { data: user, isLoading, error } = useCurrentUser()

  useEffect(() => {
    const token = getAuthToken()
    
    if (!token) {
      router.push('/login')
      return
    }

    if (!isLoading) {
      if (error || !user) {
        router.push('/login')
        return
      }
      setIsAuthorizing(false)
    }
  }, [user, isLoading, error, router])

  if (isAuthorizing || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-cyan-50">
        <div className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-gradient-to-r from-blue-600 to-cyan-600 rounded-full flex items-center justify-center">
            <Loader2 className="h-8 w-8 text-white animate-spin" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Loading Dashboard...</h2>
            <p className="text-gray-600">Please wait while we verify your access</p>
          </div>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
