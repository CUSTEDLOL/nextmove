"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, CheckSquare, Calendar, Settings, LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";

const TABS = [
  { label: "Home",     href: "/dashboard", icon: LayoutDashboard },
  { label: "Tasks",    href: "/tasks",     icon: CheckSquare },
  { label: "Matrix",   href: "/matrix",    icon: LayoutGrid },
  { label: "Calendar", href: "/calendar",  icon: Calendar },
  { label: "Settings", href: "/settings",  icon: Settings },
];

export function BottomTabBar() {
  const pathname = usePathname();

  return (
    <nav
      className="md:hidden fixed bottom-0 left-0 right-0 px-2 pb-safe"
      style={{
        background: "var(--sidebar-bg)",
        borderTop: "1px solid var(--border)",
      }}
    >
      <div className="flex items-center justify-around h-16">
        {TABS.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn("flex flex-col items-center gap-1 px-4 py-2 transition-all duration-150")}
            >
              <Icon
                className="w-5 h-5 transition-all duration-150"
                style={{ color: active ? "var(--accent)" : "var(--faint)" }}
              />
              <span
                className="text-[10px] font-medium transition-all duration-150"
                style={{
                  color: active ? "var(--accent)" : "var(--faint)",
                  fontFamily: "var(--font-sans)",
                }}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
