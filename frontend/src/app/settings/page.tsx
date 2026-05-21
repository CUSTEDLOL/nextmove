"use client";

import { useEffect, useState } from "react";
import { signOut } from "next-auth/react";
import { AppLayout } from "@/components/layout/AppLayout";
import { api } from "@/lib/api";

type SettingsUser = {
  name: string | null;
  email: string;
  timezone: string;
  study_start_hour: number;
  study_end_hour: number;
  uses_google_calendar: boolean;
  google_calendar_connected: boolean;
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsUser | null>(null);
  const [saving, setSaving] = useState(false);
  const [telegramLinked, setTelegramLinked] = useState<boolean | null>(null);
  const [telegramLoading, setTelegramLoading] = useState(false);

  useEffect(() => {
    api.getMe().then(setSettings).catch(() => setSettings(null));
    api.getTelegramLinkStatus()
      .then((res) => setTelegramLinked(res.linked))
      .catch(() => setTelegramLinked(false));
  }, []);

  async function saveSettings() {
    if (!settings) return;
    setSaving(true);
    try {
      const saved = await api.updateMe({
        name: settings.name,
        timezone: settings.timezone,
        study_start_hour: settings.study_start_hour,
        study_end_hour: settings.study_end_hour,
        uses_google_calendar: settings.uses_google_calendar,
      });
      setSettings(saved);
    } finally {
      setSaving(false);
    }
  }

  async function connectTelegram() {
    setTelegramLoading(true);
    try {
      const res = await api.getTelegramLinkToken() as { url: string };
      window.open(res.url, "_blank");
    } finally {
      setTelegramLoading(false);
    }
  }

  async function toggleCalendarConnection() {
    if (!settings) return;
    const next = settings.google_calendar_connected
      ? await api.disconnectCalendar()
      : await api.connectCalendar();
    setSettings((prev) =>
      prev
        ? {
            ...prev,
            uses_google_calendar: next.uses_google_calendar,
            google_calendar_connected: next.google_calendar_connected,
          }
        : prev
    );
  }

  return (
    <AppLayout>
      <div className="flex-1 flex flex-col max-w-2xl w-full mx-auto px-4 md:px-8 py-8 pb-24 md:pb-8 gap-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold" style={{ color: "var(--foreground)" }}>Settings</h1>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-sm font-medium px-4 py-2 rounded-[var(--radius-md)] transition-all duration-150"
            style={{ border: "1px solid var(--border)", color: "var(--muted)" }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--destructive)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--destructive)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.color = "var(--muted)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
            }}
          >
            Sign out
          </button>
        </div>

        {!settings ? (
          <div className="rounded-xl p-6 text-sm" style={{ border: "1px solid var(--border)", background: "var(--surface-elevated)", color: "var(--muted)" }}>
            Loading your settings...
          </div>
        ) : (
          <>
            <div className="rounded-xl border border-[var(--border)] bg-white p-5 space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-900">Account</p>
                <p className="text-xs text-gray-500 mt-1">Your name and timezone for scheduling.</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Name</span>
                  <input
                    value={settings.name ?? ""}
                    onChange={(event) => setSettings((prev) => prev ? { ...prev, name: event.target.value } : prev)}
                    className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-gray-900 outline-none focus:border-emerald-400"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Timezone</span>
                  <input
                    value={settings.timezone}
                    onChange={(event) => setSettings((prev) => prev ? { ...prev, timezone: event.target.value } : prev)}
                    className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-gray-900 outline-none focus:border-emerald-400"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Study start</span>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={settings.study_start_hour}
                    onChange={(event) => setSettings((prev) => prev ? { ...prev, study_start_hour: Number(event.target.value) } : prev)}
                    className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-gray-900 outline-none focus:border-emerald-400"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Study end</span>
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={settings.study_end_hour}
                    onChange={(event) => setSettings((prev) => prev ? { ...prev, study_end_hour: Number(event.target.value) } : prev)}
                    className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-gray-900 outline-none focus:border-emerald-400"
                  />
                </label>
              </div>
            </div>

            <div className="rounded-xl border border-[var(--border)] bg-white p-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">Google Calendar</p>
                  <p className="text-xs text-gray-500 mt-1">Use your Google calendar to calculate free slots and rebuild the day.</p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                  settings.google_calendar_connected ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
                }`}>
                  {settings.google_calendar_connected ? "Connected" : "Not connected"}
                </span>
              </div>
              <label className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">Use Google availability</p>
                  <p className="text-xs text-gray-500 mt-1">When enabled, schedule rebuilds look at Google Calendar first.</p>
                </div>
                <input
                  type="checkbox"
                  checked={settings.uses_google_calendar}
                  onChange={(event) =>
                    setSettings((prev) => prev ? { ...prev, uses_google_calendar: event.target.checked } : prev)
                  }
                />
              </label>
              <button
                onClick={toggleCalendarConnection}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                {settings.google_calendar_connected ? "Disconnect Google Calendar" : "Connect saved Google account"}
              </button>
            </div>

            <div className="rounded-xl border border-[var(--border)] bg-white p-5 space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">Telegram Bot</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Get task nudges and control NextMove directly from Telegram.
                  </p>
                </div>
                <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                  telegramLinked ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
                }`}>
                  {telegramLinked === null ? "Checking..." : telegramLinked ? "Connected" : "Not connected"}
                </span>
              </div>
              {!telegramLinked && (
                <button
                  onClick={connectTelegram}
                  disabled={telegramLoading}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {telegramLoading ? "Opening Telegram..." : "Connect Telegram"}
                </button>
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={saveSettings}
                disabled={saving}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save settings"}
              </button>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
