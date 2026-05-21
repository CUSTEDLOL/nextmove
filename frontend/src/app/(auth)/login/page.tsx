"use client"
import { useEffect, useState } from "react"
import { signIn, useSession } from "next-auth/react"
import { useRouter } from "next/navigation"

export default function LoginPage() {
  const router = useRouter()
  const { data: session, status } = useSession()
  const hasAccessToken = Boolean((session as { accessToken?: string } | null)?.accessToken)
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [name, setName] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (hasAccessToken) router.replace("/dashboard")
  }, [hasAccessToken, router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    setLoading(true)
    const result = await signIn("credentials", {
      redirect: false,
      email,
      password,
      name,
      action: isLogin ? "login" : "register",
    })
    if (result?.error) {
      setLoading(false)
      setError(isLogin ? "Invalid email or password." : "Could not create account.")
    } else {
      router.refresh() // flush session cookie into useSession before redirect
    }
  }

  if (status === "loading" || hasAccessToken) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--background)", color: "var(--muted)", fontSize: "0.875rem" }}>
        Loading...
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4" style={{ background: "var(--background)" }}>
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl mb-4" style={{ background: "var(--accent)" }}>
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" />
            </svg>
          </div>
          <h1 className="font-display-italic" style={{ fontSize: "2rem", lineHeight: 1, color: "var(--foreground)" }}>
            NextMove
          </h1>
          <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>
            Focus on what matters today.
          </p>
        </div>

        {/* Card */}
        <div
          className="rounded-2xl p-8"
          style={{
            background: "var(--surface-elevated)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-raised)",
          }}
        >

          {/* Email form */}
          <form onSubmit={handleSubmit} className="space-y-3">
            {!isLogin && (
              <input
                type="text"
                placeholder="Your name"
                value={name}
                onChange={e => setName(e.target.value)}
                required
                className="auth-input"
              />
            )}
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              className="auth-input"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="auth-input"
            />

            {error && (
              <p className="text-xs" style={{ color: "var(--destructive)" }}>{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl text-sm font-semibold transition-all duration-150 hover:brightness-110 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: "var(--accent)", color: "#fff" }}
            >
              {loading ? "Loading…" : isLogin ? "Sign In" : "Create Account"}
            </button>
          </form>

          <p className="text-center text-xs mt-5" style={{ color: "var(--muted)" }}>
            {isLogin ? "No account? " : "Have an account? "}
            <button
              onClick={() => { setIsLogin(!isLogin); setError("") }}
              className="transition-colors duration-150 hover:underline"
              style={{ color: "var(--accent)" }}
            >
              {isLogin ? "Sign up free" : "Sign in"}
            </button>
          </p>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: "var(--faint)" }}>
          By continuing, you agree to our terms of service.
        </p>
      </div>
    </div>
  )
}
