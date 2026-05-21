"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { signOut } from "next-auth/react"

const NAV = [
  { href: "/dashboard", label: "Today" },
  { href: "/tasks", label: "Tasks" },
  { href: "/schedule", label: "Schedule" },
]

export function Navbar() {
  const path = usePathname()
  return (
    <nav className="border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
        <Link href="/dashboard" className="font-bold text-white text-lg tracking-tight">
          NextMove
        </Link>
        <div className="flex items-center gap-6 text-sm">
          {NAV.map(n => (
            <Link
              key={n.href}
              href={n.href}
              className={path === n.href ? "text-white font-medium" : "text-zinc-500 hover:text-zinc-300 transition"}
            >
              {n.label}
            </Link>
          ))}
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-zinc-600 hover:text-zinc-400 transition text-xs"
          >
            Sign out
          </button>
        </div>
      </div>
    </nav>
  )
}
