import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

// Vite environment variable
const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const LOGIN_PATH = '/auth/login'
const TOKEN_KEY = 'token'
const ROLE_KEY = 'role'

const api = axios.create({
  baseURL: API_URL,
  timeout: 15000,
})

const ROLES = [
  {
    value: 'user',
    label: 'Developer',
    description: 'Build & share verified skill cards',
  },
  {
    value: 'recruiter',
    label: 'Recruiter',
    description: 'Discover talent by proven skills',
  },
  {
    value: 'admin',
    label: 'Admin',
    description: 'Manage users & platform settings',
  },
]

function Login({ onLogin }) {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    identifier: '',
    password: '',
    role: 'user',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    setError('')
  }

  const validate = () => {
    if (!API_URL) {
      return 'API address is missing. Add VITE_API_URL to your .env file and restart the server.'
    }
    if (!form.identifier.trim()) return 'Please enter your username or email.'
    if (!form.password) return 'Please enter your password.'
    if (!form.role) return 'Please select a role.'
    return ''
  }

  const getErrorMessage = (err) => {
    if (err.code === 'ECONNABORTED') return 'Server took too long to respond. Please try again.'
    if (!err.response) return 'Unable to reach the server. Check your connection and API URL.'
    const { status, data } = err.response
    if (status === 401 || status === 403) return 'Incorrect username, password, or role.'
    if (status === 429) return 'Too many attempts. Please wait a moment and try again.'
    return data?.message || data?.detail || `Something went wrong (${status}).`
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    const problem = validate()
    if (problem) {
      setError(problem)
      return
    }

    setLoading(true)
    setError('')

    try {
      const { data } = await api.post(LOGIN_PATH, {
        username: form.identifier.trim(),
        password: form.password,
        role: form.role, // remove this line if your backend does not expect role
      })

      // Prefer role from server, fallback to selected role
      const role = data?.role || data?.user?.role || form.role
      const token = data?.token || data?.access_token

      if (token) {
        try {
          localStorage.setItem(TOKEN_KEY, token)
          localStorage.setItem(ROLE_KEY, role)
        } catch (storageErr) {
          console.warn('Could not save login data', storageErr)
        }
      }

      // Notify parent (App.jsx)
      onLogin?.({
        ...data,
        role,
        token,
      })

      // Redirect based on role
      if (role === 'admin') {
        navigate('/admin')
      } else if (role === 'recruiter') {
        navigate('/recruiter')
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const inputBase =
    'mt-1.5 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-4 focus:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-blue-400 dark:focus:ring-blue-400/20 transition'

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 px-4 py-12">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-8 shadow-xl shadow-slate-200/50 backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/90 dark:shadow-none">
          
          {/* Header */}
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/30">
              <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Welcome back
            </h1>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Sign in to SkillProof — every claim backed by real code
            </p>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {/* Role Selection */}
            <fieldset>
              <legend className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2.5">
                I am signing in as
              </legend>
              <div className="grid grid-cols-3 gap-2">
                {ROLES.map((role) => (
                  <label
                    key={role.value}
                    className={`
                      relative flex cursor-pointer flex-col items-center rounded-xl border-2 px-2 py-3 text-center transition-all
                      ${
                        form.role === role.value
                          ? 'border-blue-600 bg-blue-50 text-blue-800 shadow-sm dark:border-blue-500 dark:bg-blue-950/50 dark:text-blue-200'
                          : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-400 dark:hover:border-slate-600'
                      }
                    `}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={role.value}
                      checked={form.role === role.value}
                      onChange={handleChange}
                      className="sr-only"
                    />
                    <span className="text-xs font-semibold leading-tight">{role.label}</span>
                    <span className="mt-1 hidden text-[10px] leading-tight opacity-70 sm:block">
                      {role.description}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            {/* Username / Email */}
            <div>
              <label htmlFor="identifier" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Username or email
              </label>
              <input
                id="identifier"
                name="identifier"
                type="text"
                value={form.identifier}
                onChange={handleChange}
                autoComplete="username"
                placeholder="you@company.com"
                className={inputBase}
              />
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="password" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Password
                </label>
                <a
                  href="/passwordreset"
                  className="text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                >
                  Forgot password?
                </a>
              </div>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={handleChange}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className={`${inputBase} pr-14`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg px-2 py-1 text-xs font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div
                role="alert"
                className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-300"
              >
                {error}
              </div>
            )}

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading}
              className="relative w-full overflow-hidden rounded-xl bg-blue-600 px-4 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-500/30 disabled:cursor-not-allowed disabled:opacity-60 dark:shadow-blue-900/40"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                    />
                  </svg>
                  Signing in…
                </span>
              ) : (
                `Sign in as ${ROLES.find((r) => r.value === form.role)?.label || form.role}`
              )}
            </button>
          </form>

          {/* Footer */}
          <p className="mt-8 text-center text-xs text-slate-400 dark:text-slate-500">
            By signing in you agree to the SkillProof Terms of Service
          </p>
        </div>

        {/* Link back to landing */}
        <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
          New here?{' '}
          <a href="/" className="font-medium text-blue-600 hover:underline dark:text-blue-400">
            Back to home
          </a>
        </p>
      </div>
    </main>
  )
}

export default Login