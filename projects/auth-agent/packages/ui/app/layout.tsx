"use client";

import { Inter } from "next/font/google";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  LayoutDashboard,
  FilePlus,
  Brain,
  ClipboardList,
  Menu,
  X,
  Shield,
} from "lucide-react";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: <LayoutDashboard size={20} /> },
  { href: "/pa/new", label: "New PA", icon: <FilePlus size={20} /> },
  {
    href: "/payers",
    label: "Payer Requirements",
    icon: <ClipboardList size={20} />,
  },
  {
    href: "/intelligence",
    label: "Payer Intelligence",
    icon: <Brain size={20} />,
  },
];

function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = usePathname();

  return (
    <aside
      className={`fixed left-0 top-0 z-30 flex h-full flex-col border-r border-slate-200 bg-white transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Shield className="h-7 w-7 text-primary-600" />
            <span className="text-lg font-bold text-primary-900">
              AuthAgent
            </span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <Menu size={20} /> : <X size={20} />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-200 p-4">
        {!collapsed && (
          <p className="text-xs text-slate-400">AuthAgent v0.1.0</p>
        )}
      </div>
    </aside>
  );
}

function DemoBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [demoMode, setDemoMode] = useState(false);

  useEffect(() => {
    fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011"}/api/config`
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.demoMode) setDemoMode(true);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  if (!demoMode || dismissed) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between bg-amber-500 px-4 py-2 text-white shadow-md">
      <span className="text-sm font-semibold tracking-wide">
        DEMO MODE &mdash; No real patient data
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="rounded p-1 hover:bg-amber-600 transition-colors"
        aria-label="Dismiss demo banner"
      >
        <X size={16} />
      </button>
    </div>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [demoVisible, setDemoVisible] = useState(false);

  useEffect(() => {
    fetch(
      `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3011"}/api/config`
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.demoMode) setDemoVisible(true);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryClientProvider client={queryClient}>
          <DemoBanner />
          <div
            className={`flex min-h-screen transition-all duration-300 ${
              demoVisible ? "pt-10" : ""
            }`}
          >
            <Sidebar
              collapsed={sidebarCollapsed}
              onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
            />
            <div
              className={`flex flex-1 flex-col transition-all duration-300 ${
                sidebarCollapsed ? "ml-16" : "ml-64"
              }`}
            >
              <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/80 px-6 backdrop-blur-sm">
                <h1 className="text-lg font-semibold text-slate-800">
                  Prior Authorization Platform
                </h1>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-500">Healthcare AI</span>
                  <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                    <span className="text-xs font-medium text-primary-700">
                      AA
                    </span>
                  </div>
                </div>
              </header>
              <main className="flex-1 p-6">{children}</main>
            </div>
          </div>
        </QueryClientProvider>
      </body>
    </html>
  );
}
