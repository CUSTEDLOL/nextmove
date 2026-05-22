import type { NextAuthOptions, User } from "next-auth"
import type { Session } from "next-auth"
import CredentialsProvider from "next-auth/providers/credentials"

interface UserWithBackendToken extends User {
  backendToken?: string
}

interface SessionWithAccessToken extends Session {
  accessToken?: string
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        name: { label: "Name", type: "text" },
        action: { label: "Action", type: "text" }, // "login" or "register"
      },
      async authorize(credentials) {
        const isRegister = credentials?.action === "register"
        const endpoint = isRegister ? "/api/auth/register" : "/api/auth/login"
        const body: Record<string, string> = {
          email: credentials!.email,
          password: credentials!.password,
        }
        if (isRegister) body.name = credentials!.name || "Student"

        const apiUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL
        if (!apiUrl) {
          console.error("[auth] BACKEND_URL and NEXT_PUBLIC_API_URL are both undefined")
          return null
        }
        try {
          const res = await fetch(`${apiUrl}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          })
          if (!res.ok) {
            console.error("[auth] Backend returned", res.status, "for", endpoint)
            return null
          }
          const data = await res.json()
          return {
            id: data.user_id || credentials!.email,
            email: credentials!.email,
            backendToken: data.access_token,
          }
        } catch (err) {
          console.error("[auth] fetch failed:", err)
          return null
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if ((user as UserWithBackendToken)?.backendToken)
        token.backendToken = (user as UserWithBackendToken).backendToken
      return token
    },
    async session({ session, token }) {
      ;(session as SessionWithAccessToken).accessToken = token.backendToken as string | undefined
      return session
    },
  },
  pages: { signIn: "/login" },
}
