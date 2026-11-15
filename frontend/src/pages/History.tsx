import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  ChevronRight,
  Filter,
  Github,
  History as HistoryIcon,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import { StatusBadge } from "../components/StatusBadge";
import { useUI } from "../lib/store";
import { formatRepo, timeAgo, useRuns } from "../lib/api";
export default function History() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const input = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [confirm, setConfirm] = useState(false);
  const samples = useUI((s) => s.samples);
  const clear = useUI((s) => s.clearSamples);
  const { data: live = [], isLoading, error } = useRuns();
  const connect = useUI((s) => s.setConnectionOpen);
  const all = [...live, ...samples].sort((a, b) =>
    b.created_at.localeCompare(a.created_at),
  );
  const runs = all.filter(
    (r) =>
      (filter === "all" ||
        (filter === "sample"
          ? r.mode === "walkthrough"
          : filter === "replay"
            ? r.mode === "replay"
            : filter === "live"
              ? r.mode === "live"
              : r.status === filter)) &&
      `${r.repo_url} ${r.issue_text} ${r.id}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  useEffect(() => {
    if (params.has("search")) input.current?.focus();
  }, [params]);
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <h1>History</h1>
        </div>
        <Button onClick={() => navigate("/new")}>
          <Plus size={16} />
          New run
        </Button>
      </div>
      {error && (
        <div className="connection-banner" role="alert">
          <span>Worker history unavailable. {error.message}</span>
          <button onClick={() => connect(true)}>Connection settings</button>
        </div>
      )}
      <div className="panel history-panel">
        <div className="table-toolbar">
          <div className="search-input">
            <Search size={16} />
            <input
              ref={input}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search repositories, issues, or run IDs…"
              aria-label="Search runs"
            />
            <kbd>/</kbd>
          </div>
          <div className="table-toolbar-actions">
            <Filter size={15} />
            <select
              aria-label="Filter runs"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All runs</option>
              <option value="ready_for_review">Needs review</option>
              <option value="running">In progress</option>
              <option value="failed">Failed</option>
              <option value="live">Live only</option>
              <option value="sample">Illustrative samples</option>
              <option value="replay">Recorded replays</option>
            </select>
            {samples.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                title="Clear local playbacks"
                aria-label="Clear local playbacks"
                onClick={() => setConfirm(true)}
              >
                <Trash2 size={15} />
              </Button>
            )}
          </div>
        </div>
        <div className="table-scroll">
          <div className="history-table-head">
            <span>REPOSITORY / ISSUE</span>
            <span>STATUS</span>
            <span>ATTEMPTS</span>
            <span>STARTED</span>
            <span />
          </div>
          {isLoading ? (
            <div className="skeleton skeleton-card" />
          ) : runs.length ? (
            runs.map((run) => (
              <Link to={`/run/${run.id}`} key={run.id} className="history-row">
                <div>
                  <strong>
                    <Github size={16} />
                    {formatRepo(run.repo_url)}
                    {run.mode === "replay" && (
                      <span className="sample-label">Recorded replay</span>
                    )}
                    {run.mode === "walkthrough" && (
                      <span className="sample-label">Illustrative sample</span>
                    )}
                  </strong>
                  <p>{run.issue_text}</p>
                </div>
                <StatusBadge status={run.status} />
                <span className="mono muted">{run.attempts.length} / 3</span>
                <span className="muted">{timeAgo(run.created_at)}</span>
                <ChevronRight size={15} />
              </Link>
            ))
          ) : (
            <div className="empty-state">
              <span className="empty-state-icon">
                <HistoryIcon size={29} />
              </span>
              <h2>
                {search || filter !== "all"
                  ? "No runs match this view"
                  : error
                    ? "Live history unavailable"
                    : "No runs yet"}
              </h2>
              <p>
                {search || filter !== "all"
                  ? "Try a different search or reset your filters."
                  : error
                    ? "Check your worker connection, then reload history."
                    : "Start a run or try an example."}
              </p>
              <Button
                variant="secondary"
                onClick={() =>
                  search || filter !== "all"
                    ? (setSearch(""), setFilter("all"))
                    : navigate("/new")
                }
              >
                {search || filter !== "all"
                  ? "Reset filters"
                  : "Start your first run"}
                <ArrowRight size={15} />
              </Button>
            </div>
          )}
        </div>
        <div className="table-footer">
          <span>
            {runs.length} of {all.length} runs
          </span>
        </div>
      </div>
      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Clear local playbacks?"
        description="This removes playback copies saved in this browser. Worker history stays unchanged."
      >
        <div className="dialog-footer">
          <Button variant="secondary" onClick={() => setConfirm(false)}>
            Keep history
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              clear();
              setConfirm(false);
              toast.success("Local playback history cleared");
            }}
          >
            Clear playbacks
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
