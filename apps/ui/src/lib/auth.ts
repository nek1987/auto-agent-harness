/**
 * Authentication Store and API
 *
 * Uses zustand for state management and httpOnly cookies for token storage.
 * Tokens are stored server-side in secure cookies, not in localStorage.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const API_BASE = '/api/auth'

// ============================================================================
// Types
// ============================================================================

interface User {
  username: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  login: (username: string, password: string) => Promise<boolean>
  logout: () => Promise<void>
  refresh: () => Promise<boolean>
  checkAuth: () => Promise<boolean>
  clearError: () => void
}

// ============================================================================
// API Functions
// ============================================================================

async function authFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<{ ok: boolean; data?: T; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      credentials: 'include', // Important: include cookies
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        ok: false,
        error: errorData.detail || `HTTP ${response.status}`,
      }
    }

    const data = await response.json()
    return { ok: true, data }
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : 'Network error',
    }
  }
}

// ============================================================================
// Auth Store
// ============================================================================

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })

        const result = await authFetch<{ username: string; message: string }>(
          '/login',
          {
            method: 'POST',
            body: JSON.stringify({ username, password }),
          }
        )

        if (result.ok && result.data) {
          set({
            user: { username: result.data.username },
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
          return true
        } else {
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
            error: result.error || 'Login failed',
          })
          return false
        }
      },

      logout: async () => {
        set({ isLoading: true })

        await authFetch('/logout', { method: 'POST' })

        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        })
      },

      refresh: async () => {
        const result = await authFetch<{ username: string; message: string }>(
          '/refresh',
          { method: 'POST' }
        )

        if (result.ok && result.data) {
          set({
            user: { username: result.data.username },
            isAuthenticated: true,
          })
          return true
        } else {
          set({
            user: null,
            isAuthenticated: false,
          })
          return false
        }
      },

      checkAuth: async () => {
        const { isAuthenticated } = get()

        // If already authenticated, try to get user info
        const result = await authFetch<{ username: string; is_active: boolean }>(
          '/me'
        )

        if (result.ok && result.data) {
          set({
            user: { username: result.data.username },
            isAuthenticated: true,
          })
          return true
        }

        // Try to refresh if not authenticated
        if (!isAuthenticated) {
          return await get().refresh()
        }

        set({
          user: null,
          isAuthenticated: false,
        })
        return false
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      // Only persist username for display, not auth state
      // (auth state comes from httpOnly cookies)
      partialize: (state) => ({
        user: state.user,
      }),
    }
  )
)

// ============================================================================
// Auth Utilities
// ============================================================================

/**
 * Hook to check if authentication is enabled on the server.
 * Returns true if auth is enabled, false if disabled.
 */
export async function isAuthEnabled(): Promise<boolean> {
  try {
    // Try to access a protected endpoint without auth
    const response = await fetch('/api/health', {
      credentials: 'include',
    })
    return response.ok
  } catch {
    return true // Assume auth is enabled if we can't check
  }
}

/**
 * Setup automatic token refresh.
 * Call this once on app startup.
 */
export function setupTokenRefresh(intervalMs: number = 14 * 60 * 1000): () => void {
  // Refresh tokens every 14 minutes (access token expires in 15)
  const intervalId = setInterval(async () => {
    const store = useAuthStore.getState()
    if (store.isAuthenticated) {
      await store.refresh()
    }
  }, intervalMs)

  return () => clearInterval(intervalId)
}
