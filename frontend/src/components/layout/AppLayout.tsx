"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Sidebar } from "./Sidebar";
import { BottomTabBar } from "./BottomTabBar";
import { ScheduleProvider } from "@/lib/schedule-store";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { data: session, status } = useSession();
  const hasAccessToken = Boolean((session as { accessToken?: string } | null)?.accessToken);

  useEffect(() => {
    if (status !== "loading" && !hasAccessToken) {
      router.replace("/login");
    }
  }, [hasAccessToken, router, status]);

  if (status === "loading" || !hasAccessToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4">
        <p className="text-sm text-gray-500">Checking your session...</p>
      </div>
    );
  }

  return (
    <ScheduleProvider>
      <div className="flex min-h-screen bg-[var(--background)]">
        <Sidebar />
        <main className="flex-1 flex flex-col min-w-0">
          {children}
        </main>
        <BottomTabBar />
      </div>
    </ScheduleProvider>
  );
}
