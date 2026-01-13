/**
 * Login Form Component
 *
 * Neobrutalism-styled login form for authentication.
 */

import { useState, FormEvent } from 'react'
import { useAuthStore } from '../lib/auth'
import { Loader2, LogIn, AlertCircle } from 'lucide-react'

export function LoginForm() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const { login, isLoading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    clearError()

    if (!username || !password) {
      return
    }

    await login(username, password)
  }

  return (
    <div className="min-h-screen bg-[var(--color-neo-bg)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo / Title */}
        <div className="text-center mb-8">
          <h1 className="font-display text-4xl font-bold tracking-tight uppercase text-[var(--color-neo-text)]">
            Auto Agent Harness
          </h1>
          <p className="text-[var(--color-neo-text-secondary)] mt-2">
            Autonomous Coding Agent Control Panel
          </p>
        </div>

        {/* Login Card */}
        <div className="neo-card p-8">
          <h2 className="font-display text-2xl font-bold mb-6 text-center">
            Sign In
          </h2>

          {/* Error Message */}
          {error && (
            <div className="neo-card bg-red-50 border-red-500 p-4 mb-6 flex items-center gap-3">
              <AlertCircle className="text-red-500 flex-shrink-0" size={20} />
              <p className="text-red-700 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Username Field */}
            <div>
              <label
                htmlFor="username"
                className="block text-sm font-bold mb-2 text-[var(--color-neo-text)]"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                autoComplete="username"
                autoFocus
                disabled={isLoading}
                className="neo-input w-full"
              />
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-bold mb-2 text-[var(--color-neo-text)]"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                disabled={isLoading}
                className="neo-input w-full"
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading || !username || !password}
              className="neo-btn neo-btn-primary w-full justify-center"
            >
              {isLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  Sign In
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-[var(--color-neo-text-secondary)] mt-8">
          Auto-Agent-Harness v2.0
        </p>
      </div>
    </div>
  )
}
