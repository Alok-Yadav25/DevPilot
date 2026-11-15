import { useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Command,
  LayoutDashboard,
  Menu,
  Moon,
  Plus,
  ShieldCheck,
  Sun,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import { MotionConfig } from "framer-motion";
import { Toaster } from "sonner";
import { useHealth, useLimits } from "../lib/api";
import { useUI } from "../lib/store";
import { Button } from "./ui/button";
import { Dialog } from "./ui/dialog";
import { ConnectionDialog } from "./ConnectionDialog";
const links = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/runs", label: "Run history", icon: Activity },
  { path: "/evaluation", label: "Evaluation", icon: BarChart3 },
  { path: "/about", label: "How it works", icon: BookOpen },
];
export function Logo() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Zap size={21} fill="currentColor" strokeWidth={1.8} />
      </span>
      <span>
        devpilot<span className="brand-period">.</span>
      </span>
    </span>
  );
}
export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    theme,
    collapsed,
    setCollapsed,
    setTheme,
    setConnectionOpen,
    shortcutsOpen,
    setShortcutsOpen,
    tick,
  } = useUI();
  const samples = useUI((s) => s.samples);
  const health = useHealth();
  const budget = useLimits();
  const ready = health.data?.ready;
  const count = samples.filter((r) => r.status === "ready_for_review").length;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [tick]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLElement &&
        (e.target.matches("input,textarea,select") ||
          e.target.isContentEditable)
      )
        return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key.toLowerCase() === "n") {
        e.preventDefault();
        navigate("/new");
      }
      if (e.key === "?") {
        e.preventDefault();
        setShortcutsOpen(true);
      }
      if (e.key === "/") {
        e.preventDefault();
        navigate("/runs?search=1");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, setShortcutsOpen]);
  useEffect(() => {
    setCollapsed(false);
    window.scrollTo(0, 0);
  }, [location.pathname, setCollapsed]);
  const current = location.pathname.startsWith("/run/")
    ? "Live run"
    : location.pathname === "/new"
      ? "New run"
      : (links.find((l) => l.path === location.pathname)?.label ?? "Workspace");
  return (
    <MotionConfig reducedMotion="user">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="app-shell">
        <aside className={`sidebar ${collapsed ? "sidebar-open" : ""}`}>
          <NavLink to="/" className="brand-link" aria-label="DevPilot home">
            <Logo />
          </NavLink>
          <button
            className="workspace-switch"
            onClick={() => setConnectionOpen(true)}
          >
            <span className="workspace-avatar">D</span>
            <span>
              <strong>Personal workspace</strong>
              <small>Local-first · Free</small>
            </span>
            <ChevronDown size={14} />
          </button>
          <div className="nav-group-title">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {links.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                end={path === "/"}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "nav-active" : ""}`
                }
              >
                <Icon size={18} />
                <span>{label}</span>
                {path === "/runs" && count > 0 && (
                  <span className="nav-counter">{count}</span>
                )}
              </NavLink>
            ))}
          </nav>
          <button className="sidebar-new" onClick={() => navigate("/new")}>
            <Plus size={17} />
            New run<kbd>N</kbd>
          </button>
          <div className="sidebar-bottom">
            {ready && (
              <div className="provider-budget">
                <span>
                  API BUDGET <small>REMAINING</small>
                </span>
                <div>
                  <span>Groq requests</span>
                  <strong>
                    {budget.data?.groq?.["x-ratelimit-remaining-requests"] ??
                      "Unknown"}
                  </strong>
                </div>
                <div>
                  <span>GitHub requests</span>
                  <strong>
                    {budget.data?.github?.["x-ratelimit-remaining"] ??
                      "Unknown"}
                  </strong>
                </div>
                <div>
                  <span>Active runs</span>
                  <strong>
                    {budget.data
                      ? `${budget.data.current_concurrent_runs} / ${budget.data.max_concurrent_runs}`
                      : "Unknown"}
                  </strong>
                </div>
                <div>
                  <span>Queued locally</span>
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
                <p>Reported after provider requests.</p>
              </div>
            )}
            <div className="sandbox-card">
              <div>
                <span className={`status-dot ${ready ? "green" : "amber"}`} />
                <strong>
                  {ready ? "Worker connected" : "Your sandbox, your rules"}
                </strong>
              </div>
              <p>
                {ready
                  ? health.data?.runner === "replay"
                    ? "Replay mode. Live execution is disabled."
                    : "Ready for isolated Python runs."
                  : "Connect a worker to run real fixes in an isolated environment."}
              </p>
              <button onClick={() => setConnectionOpen(true)}>
                {ready ? "Manage connection" : "Connect worker"}
                <ArrowUpRight size={14} />
              </button>
            </div>
            <button
              className="sidebar-help"
              onClick={() => setShortcutsOpen(true)}
            >
              <CircleHelp size={17} />
              Help & shortcuts<kbd>?</kbd>
            </button>
            <div className="profile">
              <span className="profile-avatar">Y</span>
              <div>
                <strong>Your workspace</strong>
                <small>Human in control</small>
              </div>
              <ShieldCheck size={17} />
            </div>
          </div>
        </aside>
        {collapsed && (
          <button
            className="sidebar-backdrop"
            onClick={() => setCollapsed(false)}
            aria-label="Close navigation"
          />
        )}
        <div className="app-body">
          <header className="topbar">
            <div className="breadcrumbs">
              <Button
                variant="ghost"
                size="icon"
                className="mobile-menu"
                onClick={() => setCollapsed(!collapsed)}
                aria-label="Open navigation"
              >
                {collapsed ? <X size={18} /> : <Menu size={18} />}
              </Button>
              <span className="breadcrumb-icon">
                <Terminal size={15} />
              </span>
              <span>Workspace</span>
              <ChevronRight size={13} />
              <strong>{current}</strong>
            </div>
            <div className="topbar-actions">
              <span className="environment-tag">
                <span className={`status-dot ${ready ? "green" : "violet"}`} />
                {ready ? "Live worker" : "Explore workspace"}
              </span>
              <button
                className="icon-control theme-toggle"
                onClick={setTheme}
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
              </button>
              <span className="topbar-divider" />
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate("/new")}
              >
                <Plus size={15} />
                New run
              </Button>
            </div>
          </header>
          <main id="main" tabIndex={-1}>
            {["waking", "reconnecting", "offline", "error"].includes(
              useUI.getState().connectionState,
            ) && (
              <div
                className="connection-banner"
                role="status"
                aria-live="polite"
              >
                {useUI.getState().connectionState === "waking"
                  ? "Waking up the server. This can take about a minute. Your action will continue automatically."
                  : useUI.getState().connectionState === "reconnecting"
                    ? "Reconnecting to the worker. Run history stays saved."
                    : useUI.getState().connectionState === "offline"
                      ? "You are offline. Reconnect and retry your action."
                      : "Worker connection unavailable. Check its API address and try again."}
              </div>
            )}
            <Outlet />
          </main>
          <footer className="app-footer">
            <span>
              <ShieldCheck size={13} /> Built for autonomy. Designed for
              oversight.
            </span>
            <span className="footer-right">
              <span className="status-dot green" />
              Python + pytest<span className="footer-dot">·</span>DevPilot v1.0
            </span>
          </footer>
        </div>
      </div>
      <ConnectionDialog />
      <Dialog
        open={shortcutsOpen}
        onOpenChange={setShortcutsOpen}
        title="A little less clicking"
        description="Keyboard shortcuts for your workspace."
      >
        <div className="shortcut-list">
          {[
            ["N", "Start a new run"],
            ["/", "Search run history"],
            ["A", "Approve a reviewed patch"],
            ["R", "Reject a reviewed patch"],
            ["?", "Show these shortcuts"],
          ].map(([key, label]) => (
            <div key={key}>
              <span>{label}</span>
              <kbd>{key}</kbd>
            </div>
          ))}
        </div>
        <p className="field-help">
          <Command size={13} /> Shortcuts pause while you’re typing. Approval
          shortcuts only work when a run is ready for review.
        </p>
      </Dialog>
      <Toaster richColors theme={theme} position="bottom-right" closeButton />
    </MotionConfig>
  );
}
