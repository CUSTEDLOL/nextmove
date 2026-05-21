"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CheckSquare, Calendar, Settings, Zap, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Tasks",     href: "/tasks",     icon: CheckSquare },
  { label: "Matrix",    href: "/matrix",    icon: LayoutGrid },
  { label: "Calendar",  href: "/calendar",  icon: Calendar },
  { label: "Settings",  href: "/settings",  icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const [user, setUser] = useState<{ name?: string | null; email?: string; timezone?: string } | null>(null);

  useEffect(() => {
    api.getMe().then(setUser).catch(() => setUser(null));
  }, []);

  const base = user?.name || user?.email || "NM";
  const initials =
    base
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "NM";

  return (
    <aside
      className="hidden md:flex flex-col w-[220px] min-h-screen border-r px-3 py-6"
      style={{
        background: "var(--sidebar-bg)",
        borderColor: "var(--border)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-8 px-3">
        <div
          className="w-6 h-6 rounded-md flex items-center justify-center shrink-0"
          style={{ background: "var(--accent)" }}
        >
          <Zap className="w-3.5 h-3.5 text-white" fill="white" />
        </div>
        <span
          className="font-semibold text-[15px] tracking-tight"
          style={{ color: "var(--foreground)", fontFamily: "var(--font-sans)" }}
        >
          NextMove
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 flex-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 py-2.5 rounded-lg text-sm transition-all duration-150",
                // Border-left active indicator — no layout shift via pl offset
                active
                  ? "border-l-[3px] pl-[9px] pr-3"
                  : "border-l-[3px] pl-[9px] pr-3"
              )}
              style={
                active
                  ? {
                      borderColor: "var(--accent)",
                      background: "var(--surface-elevated)",
                      color: "var(--foreground)",
                      fontWeight: 500,
                      boxShadow: "var(--shadow-card)",
                    }
                  : {
                      borderColor: "transparent",
                      color: "var(--muted)",
                    }
              }
              onMouseEnter={e => {
                if (!active) {
                  (e.currentTarget as HTMLAnchorElement).style.color = "var(--foreground)";
                  (e.currentTarget as HTMLAnchorElement).style.background = "rgba(255,255,255,0.45)";
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  (e.currentTarget as HTMLAnchorElement).style.color = "var(--muted)";
                  (e.currentTarget as HTMLAnchorElement).style.background = "transparent";
                }
              }}
            >
              <Icon
                className="w-4 h-4 shrink-0"
                style={{ color: active ? "var(--accent)" : "var(--faint)" }}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div
        className="flex items-center gap-3 px-3 pt-4"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
          style={{ background: "var(--accent)", color: "#ffffff" }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: "var(--foreground)" }}>
            {user?.name || "NextMove user"}
          </p>
          <p className="text-xs truncate" style={{ color: "var(--faint)" }}>
            {user?.email || user?.timezone || "Not connected"}
          </p>
        </div>
      </div>
    </aside>
  );
}
