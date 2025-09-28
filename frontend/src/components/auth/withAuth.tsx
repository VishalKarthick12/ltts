'use client'

import { ComponentType } from 'react'
import ProtectedRoute from './ProtectedRoute'

interface WithAuthOptions {
  requireAuth?: boolean
  redirectTo?: string
  loadingComponent?: React.ReactNode
}

export function withAuth<P extends object>(
  Component: ComponentType<P>,
  options: WithAuthOptions = {}
) {
  const { requireAuth = true, redirectTo = '/login' } = options

  const AuthenticatedComponent = (props: P) => {
    return (
      <ProtectedRoute 
        requireAuth={requireAuth} 
        redirectTo={redirectTo}
      >
        <Component {...props} />
      </ProtectedRoute>
    )
  }

  // Set display name for debugging
  AuthenticatedComponent.displayName = `withAuth(${Component.displayName || Component.name})`

  return AuthenticatedComponent
}
