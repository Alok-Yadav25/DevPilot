import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  Cable,
  CircleHelp,
  LayoutDashboard,
  Menu,
  Moon,
  Plus,
  Sun,
  X,
} from "lucide-react";
import { MotionConfig } from "framer-motion";
import { Toaster } from "sonner";
import { useHealth, useLimits } from "../lib/api";
import { getToken, useUI } from "../lib/store";
import { ApiError } from "../lib/client";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { ConnectionDialog } from "./ConnectionDialog";
import { Logo, CreatorCredit } from "./Brand";
const links = [
  { path: "/workspace", label: "Overview", icon: LayoutDashboard },
  { path: "/runs", label: "History", icon: Activity },
  { path: "/evaluation", label: "Evaluation", icon: BarChart3 },
  { path: "/about", label: "How it works", icon: BookOpen },
];
export default function Layout() {
  const navigate = useNavigate(),
    location = useLocation();
  const {
    theme,
    collapsed,
    setCollapsed,
    setTheme,
    setConnectionOpen,
    shortcutsOpen,
    setShortcutsOpen,
    tick,
    connectionState,
  } = useUI();
  const sidebarRef = useRef<HTMLElement>(null);
  const appBodyRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const health = useHealth(),
    budget = useLimits();
  const playback = /^\/run\/(?:sample-|recording-)/.test(location.pathname);
  const denied =
    budget.error instanceof ApiError &&
    [401, 403].includes(budget.error.status);
  const ready = !!health.data?.ready && !!getToken() && !denied;
  const label = denied
    ? "Check access"
    : health.data?.runner === "replay"
      ? "Replay mode"
      : ready
        ? "Worker ready"
        : health.data && !health.data.ready
          ? "Setup needed"
          : "Connect worker";
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [tick]);
  useEffect(() => {
    if (!collapsed || !window.matchMedia("(max-width: 780px)").matches) return;
    const body = appBodyRef.current;
    const sidebar = sidebarRef.current;
    if (!body || !sidebar) return;
    body.inert = true;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const controls = () =>
      [
        ...sidebar.querySelectorAll<HTMLElement>("a[href], button, summary"),
      ].filter((element) => element.getClientRects().length);
    controls()[0]?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setCollapsed(false);
      }
      if (event.key !== "Tab") return;
      const items = controls(),
        first = items[0],
        last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    const viewport = window.matchMedia("(max-width: 780px)");
    const resize = () => setCollapsed(false);
    viewport.addEventListener("change", resize);
    window.addEventListener("keydown", key);
    return () => {
      viewport.removeEventListener("change", resize);
      body.inert = false;
      document.body.style.overflow = overflow;
      window.removeEventListener("keydown", key);
      menuRef.current?.focus();
    };
  }, [collapsed, setCollapsed]);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (
        document.querySelector('[role="dialog"]') ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey
      )
        return;
      if (
        event.target instanceof HTMLElement &&
        (event.target.matches("input,textarea,select") ||
          event.target.isContentEditable)
      )
        return;
      if (event.key.toLowerCase() === "n") {
        event.preventDefault();
        navigate("/new");
      }
      if (event.key === "?") {
        event.preventDefault();
        setShortcutsOpen(true);
      }
      if (event.key === "/") {
        event.preventDefault();
        navigate("/runs?search=1");
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [navigate, setShortcutsOpen]);
  useEffect(() => {
    setCollapsed(false);
    window.scrollTo(0, 0);
  }, [location.pathname, setCollapsed]);
  const current = location.pathname.startsWith("/run/")
    ? "Run"
    : location.pathname === "/new"
      ? "New run"
      : (links.find((l) => l.path === location.pathname)?.label ?? "DevPilot");
  return (
    <MotionConfig reducedMotion="user">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="app-shell minimal-shell">
        <aside
          id="main-sidebar"
          ref={sidebarRef}
          className={`sidebar ${collapsed ? "sidebar-open" : ""}`}
        >
          <NavLink to="/" className="brand-link" aria-label="DevPilot home">
            <Logo />
          </NavLink>
          <nav aria-label="Main navigation">
            {links.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                end={path === "/workspace"}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "nav-active" : ""}`
                }
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            {ready && health.data?.runner !== "replay" && (
              <details className="usage-details">
                <summary>Usage</summary>
                <div className="provider-budget">
                  <div>
                    <span>Groq remaining</span>
                    <strong>
                      {budget.data?.groq?.["x-ratelimit-remaining-requests"] ??
                        "Unknown"}
                    </strong>
                  </div>
                  <div>
                    <span>GitHub remaining</span>
                    <strong>
                      {budget.data?.github?.["x-ratelimit-remaining"] ??
                        "Unknown"}
                    </strong>
                  </div>
                  <div>
                    <span>Active</span>
                    <strong>
                      {budget.data
                        ? `${budget.data.current_concurrent_runs} / ${budget.data.max_concurrent_runs}`
                        : "Unknown"}
                    </strong>
                  </div>
                  <div>
                    <span>Queued</span>
                    <strong>{budget.data?.queued_runs ?? "Unknown"}</strong>
                  </div>
                  {health.data?.runner === "github_actions" && (
                    <div>
                      <span>Actions queue</span>
                      <strong>
                        {budget.data?.github_queued_jobs ?? "Unknown"}
                      </strong>
                    </div>
                  )}
                </div>
              </details>
            )}
            <button
              className="connection-trigger"
              onClick={() => {
                setCollapsed(false);
                setConnectionOpen(true);
              }}
            >
              <Cable size={17} />
              <span>{label}</span>
              <span className={`status-dot ${ready ? "green" : "amber"}`} />
            </button>
            <button
              className="sidebar-help"
              onClick={() => {
                setCollapsed(false);
                setShortcutsOpen(true);
              }}
            >
              <CircleHelp size={17} />
              Shortcuts<kbd>?</kbd>
            </button>
          </div>
        </aside>
        {collapsed && (
          <button
            className="sidebar-backdrop"
            onClick={() => setCollapsed(false)}
            aria-label="Close navigation"
          />
        )}
        <div className="app-body" ref={appBodyRef}>
          <header className="topbar">
            <div className="breadcrumbs">
              <Button
                variant="ghost"
                size="icon"
                className="mobile-menu"
                ref={menuRef}
                aria-controls="main-sidebar"
                aria-expanded={collapsed}
                onClick={() => setCollapsed(!collapsed)}
                aria-label={collapsed ? "Close navigation" : "Open navigation"}
              >
                {collapsed ? <X size={18} /> : <Menu size={18} />}
              </Button>
              <strong>{current}</strong>
            </div>
            <div className="topbar-actions">
              <button
                className="icon-control theme-toggle"
                onClick={setTheme}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              {!["/workspace", "/new"].includes(location.pathname) && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate("/new")}
                >
                  <Plus size={16} />
                  New run
                </Button>
              )}
            </div>
          </header>
          <main id="main" tabIndex={-1}>
            {!playback && connectionState !== "connected" && (
              <div
                className="connection-banner"
                role="status"
                aria-live="polite"
              >
                <span>
                  {connectionState === "waking"
                    ? "Waking worker… Your action will continue automatically."
                    : connectionState === "reconnecting"
                      ? "Reconnecting…"
                      : connectionState === "offline"
                        ? "You’re offline. Reconnect to continue."
                        : "Worker unavailable. Check your connection."}
                </span>
                {["error", "offline"].includes(connectionState) && (
                  <button
                    onClick={() => {
                      setCollapsed(false);
                      setConnectionOpen(true);
                    }}
                  >
                    Connection settings
                  </button>
                )}
              </div>
            )}
            <Outlet />
          </main>
          <footer className="workspace-credit">
            <CreatorCredit />
          </footer>
        </div>
      </div>
      <ConnectionDialog />
      <Dialog
        open={shortcutsOpen}
        onOpenChange={setShortcutsOpen}
        title="Keyboard shortcuts"
      >
        <div className="shortcut-list">
          {[
            ["N", "New run"],
            ["/", "Search history"],
            ["A", "Approve patch"],
            ["R", "Reject patch"],
            ["?", "Shortcuts"],
          ].map(([key, label]) => (
            <div key={key}>
              <span>{label}</span>
              <kbd>{key}</kbd>
            </div>
          ))}
        </div>
        <p className="field-help">Approval keys open a confirmation dialog.</p>
      </Dialog>
      <Toaster richColors theme={theme} position="bottom-right" closeButton />
    </MotionConfig>
  );
}
