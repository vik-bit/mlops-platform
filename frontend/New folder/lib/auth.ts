/**
 * Authentication utility functions
 * Handles token management and auth state
 */

export const getAuthToken = (): string | null => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('authToken')
}

export const setAuthToken = (token: string): void => {
  if (typeof window === 'undefined') return
  localStorage.setItem('authToken', token)
}

export const removeAuthToken = (): void => {
  if (typeof window === 'undefined') return
  localStorage.removeItem('authToken')
  localStorage.removeItem('user')
}

export const getUser = () => {
  if (typeof window === 'undefined') return null
  const user = localStorage.getItem('user')
  return user ? JSON.parse(user) : null
}

export const setUser = (user: any): void => {
  if (typeof window === 'undefined') return
  localStorage.setItem('user', JSON.stringify(user))
}

export const isAuthenticated = (): boolean => {
  return !!getAuthToken()
}

/**
 * Make authenticated API calls
 * Automatically includes Authorization header
 */
export const authenticatedFetch = async (
  url: string,
  options: RequestInit = {}
) => {
  const token = getAuthToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(typeof options.headers === 'object' && !Array.isArray(options.headers)
      ? (options.headers as Record<string, string>)
      : {}),
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  // If 401, token may be invalid
  if (response.status === 401) {
    removeAuthToken()
    if (typeof window !== 'undefined') {
      window.location.href = '/auth/login'
    }
  }

  return response
}
