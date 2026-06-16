'use client'

/**
 * Login page — wired to POST /login on the API Gateway.
 *
 * Auth flow:
 *   1. Submit username + password as form-encoded (OAuth2PasswordRequestForm)
 *   2. Gateway returns { access_token, token_type }
 *   3. Store as "mlops_token" — the key api.ts reads for Bearer auth
 *   4. Redirect to dashboard
 *
 * Uses auth.login() from api.ts — do NOT call fetch('/api/auth/login') directly:
 *   - That hits a Next.js API route that doesn't exist
 *   - The gateway expects form-encoded, not JSON — auth.login() handles encoding
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Brain, User, Lock, AlertCircle, Loader2, Eye, EyeOff, Zap } from 'lucide-react'
import { auth, setToken } from '@/lib/api';


interface FormData { username: string; password: string }
interface FieldErrors { username?: string; password?: string; submit?: string }

export default function LoginPage() {
  const router = useRouter()
  const [form, setForm]                 = useState<FormData>({ username: '', password: '' })
  const [errors, setErrors]             = useState<FieldErrors>({})
  const [loading, setLoading]           = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  function validate(): boolean {
    const e: FieldErrors = {}
    if (!form.username.trim())         e.username = 'Username is required'
    else if (form.username.length < 3) e.username = 'Must be at least 3 characters'
    if (!form.password.trim())         e.password = 'Password is required'
    else if (form.password.length < 6) e.password = 'Must be at least 6 characters'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: value }))
    if (errors[name as keyof FieldErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }))
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    setErrors({})

    try {
      // auth.login() sends form-encoded to POST /login — NOT /api/auth/login
      // Response: { access_token: string, token_type: "bearer" }
      const data = await auth.login(form.username, form.password)

      // Must use "mlops_token" — the exact key api.ts reads for Bearer injection
      setToken(data.access_token)

      router.push('/')
    } catch (err: unknown) {
      let msg = 'Login failed. Check your credentials.'
      if (err instanceof Error) {
        if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
          msg = `Cannot reach the API Gateway at ${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}. Is it running?`
        } else if (err.message.includes('401') || err.message.includes('Invalid')) {
          msg = 'Incorrect username or password.'
        } else if (err.message.includes('422')) {
          msg = 'Request format error — contact support.'
        } else {
          msg = err.message
        }
      }
      setErrors({ submit: msg })
    } finally {
      setLoading(false)
    }
  }

  function fillDemo() {
    setForm({ username: 'admin', password: 'admin123' })
    setErrors({})
  }

  return (
    <div className="min-h-screen bg-[#0b0d11] flex items-center justify-center px-4 py-12">

      {/* Subtle ambient glows */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
        <div className="absolute top-[-20%] left-[30%] w-[600px] h-[600px] rounded-full bg-blue-600/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[20%] w-[400px] h-[400px] rounded-full bg-indigo-600/5 blur-[100px]" />
      </div>

      <div className="w-full max-w-sm relative z-10">

        {/* Logo + title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 mb-4 shadow-lg shadow-blue-500/20">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-semibold text-zinc-100 tracking-tight">NexusML</h1>
          <p className="text-sm text-zinc-500 mt-1">Sign in to your MLOps workspace</p>
        </div>

        {/* Card */}
        <div className="bg-[#12151c] border border-white/[0.07] rounded-2xl p-7 shadow-2xl shadow-black/40">

          {/* Submit error banner */}
          {errors.submit && (
            <div className="flex items-start gap-3 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-5">
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-400 leading-relaxed">{errors.submit}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Username */}
            <div>
              <label
                htmlFor="username"
                className="block text-[10px] font-medium text-zinc-500 mb-1.5 uppercase tracking-widest"
              >
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600 pointer-events-none" />
                <input
                  id="username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  value={form.username}
                  onChange={handleChange}
                  placeholder="your-username"
                  disabled={loading}
                  className={[
                    'w-full bg-[#0b0d11] border rounded-lg pl-9 pr-4 py-2.5 text-sm text-zinc-200',
                    'placeholder:text-zinc-700 transition-all disabled:opacity-50',
                    'focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/40',
                    errors.username
                      ? 'border-red-500/40 bg-red-500/5'
                      : 'border-white/[0.08] hover:border-white/[0.15]',
                  ].join(' ')}
                />
              </div>
              {errors.username && (
                <p className="text-[11px] text-red-400 mt-1.5 flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-red-400 flex-shrink-0" />
                  {errors.username}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-[10px] font-medium text-zinc-500 mb-1.5 uppercase tracking-widest"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600 pointer-events-none" />
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  disabled={loading}
                  className={[
                    'w-full bg-[#0b0d11] border rounded-lg pl-9 pr-10 py-2.5 text-sm text-zinc-200',
                    'placeholder:text-zinc-700 transition-all disabled:opacity-50',
                    'focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/40',
                    errors.password
                      ? 'border-red-500/40 bg-red-500/5'
                      : 'border-white/[0.08] hover:border-white/[0.15]',
                  ].join(' ')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  disabled={loading}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-600 hover:text-zinc-400 transition-colors disabled:opacity-50"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-[11px] text-red-400 mt-1.5 flex items-center gap-1.5">
                  <span className="w-1 h-1 rounded-full bg-red-400 flex-shrink-0" />
                  {errors.password}
                </p>
              )}
            </div>

            {/* Sign in button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 bg-blue-600 hover:bg-blue-500 active:bg-blue-700
                disabled:opacity-60 disabled:cursor-not-allowed
                text-white text-sm font-medium py-2.5 px-4 rounded-lg
                flex items-center justify-center gap-2 transition-all
                shadow-lg shadow-blue-600/20 hover:shadow-blue-500/30"
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" />Signing in…</>
                : 'Sign in'
              }
            </button>

          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-white/[0.06]" />
            <span className="text-[10px] text-zinc-700 uppercase tracking-widest">or</span>
            <div className="flex-1 h-px bg-white/[0.06]" />
          </div>

          {/* Demo fill button */}
          <button
            type="button"
            onClick={fillDemo}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2
              border border-white/[0.08] hover:border-white/[0.14] hover:bg-white/[0.03]
              text-zinc-500 hover:text-zinc-300 text-sm font-medium
              py-2.5 px-4 rounded-lg transition-all disabled:opacity-50"
          >
            <Zap className="w-3.5 h-3.5" />
            Fill demo credentials
          </button>

        </div>

        {/* Gateway URL — visible hint for developers */}
        <p className="text-center text-[10px] text-zinc-800 mt-5 font-mono tracking-wide">
          gateway → {process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'}
        </p>

      </div>
    </div>
  )
}