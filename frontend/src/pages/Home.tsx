import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ChevronRight, Github, Play } from "lucide-react";
import { Button } from "../components/ui/button";
import { StatusBadge } from "../components/StatusBadge";
import { ExampleCards } from "../components/Examples";
import { useUI } from "../lib/store";
import { api, formatRepo, timeAgo, useRecordings, useRuns } from "../lib/api";
import type { Run } from "../lib/types";
import NewRun from "./NewRun";
export function RecordedRuns() {
  const recordings = useRecordings();
  const navigate = useNavigate();
  const start = useUI((s) => s.startRecorded);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  return (
    <section className="recordings-section">
      <div className="section-heading">
        <div>
          <h2>Recorded runs</h2>
          <p>Replay saved investigations with their original test evidence.</p>
        </div>
      </div>
      {recordings.data?.length ? (
        <div className="panel">
          {recordings.data.map((record) => (
            <button
              className="recording-row"
              key={record.id}
              disabled={!!busy}
              onClick={async () => {
                setBusy(record.id);
                setError("");
                try {
                  navigate(
                    `/run/${start(await api<Run>(`/replays/${record.id}`))}`,
                  );
                } catch (e) {
                  setError(
                    e instanceof Error
                      ? e.message
                      : "Recording could not load. Reconnect and retry.",
                  );
                } finally {
                  setBusy("");
                }
              }}
            >
              <Play size={16} />
              <span>
                <strong>{formatRepo(record.repo_url)}</strong>
                <small>
                  Recorded real run ·{" "}
                  {new Date(record.recorded_at).toLocaleDateString()}
                </small>
              </span>
              <span>{busy === record.id ? "Loading…" : "Replay"}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="field-help">
          {recordings.error
            ? "Connect the worker to load real recordings. Illustrative examples work locally."
            : recordings.isLoading
              ? "Loading recordings…"
              : "No recorded real runs yet. Illustrative examples are available below."}
        </p>
      )}
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
    </section>
  );
}
export default function Home() {
  const [examples, setExamples] = useState(false);
  const runsQuery = useRuns();
  const runs = runsQuery.data ?? [];
  const approvals = runs.filter((run) => run.approved).length;
  return (
    <div className="page home-page workspace-overview">
      <header className="page-heading">
        <div>
          <div className="eyebrow">WORKSPACE</div>
          <h1>What are we fixing?</h1>
          <p>Start with a Python repository and a reproducible bug.</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => setExamples(!examples)}
          aria-expanded={examples}
        >
          Try an example
        </Button>
      </header>
      {examples && (
        <section className="examples-section">
          <div className="section-heading">
            <div>
              <h2>Illustrative examples</h2>
              <p>Scripted walkthroughs. No real repository or model is used.</p>
            </div>
          </div>
          <ExampleCards compact />
        </section>
      )}
      <NewRun embedded />
      <section className="activity-section">
        <div className="section-heading">
          <div>
            <h2>Recent runs</h2>
            <p>
              {runs.length
                ? `${runs.length} loaded live runs · Approval rate ${Math.round((approvals / runs.length) * 100)}%`
                : "Your investigations and decisions will appear here."}
            </p>
          </div>
          <Link className="text-link" to="/runs">
            View history <ArrowRight size={16} />
          </Link>
        </div>
        <div className="panel recent-runs">
          {runs.length ? (
            runs.slice(0, 5).map((run) => (
              <Link className="run-row" key={run.id} to={`/run/${run.id}`}>
                <span>
                  <strong>
                    <Github size={16} />
                    {formatRepo(run.repo_url)}
                  </strong>
                  <small>{run.issue_text}</small>
                </span>
                <StatusBadge status={run.status} />
                <span className="muted">{timeAgo(run.created_at)}</span>
                <ChevronRight size={16} />
              </Link>
            ))
          ) : (
            <div className="recent-empty">
              <div>
                <h3>
                  {runsQuery.data
                    ? "No runs yet"
                    : "Connect your worker to load history"}
                </h3>
                <p>
                  Start an investigation above, or try an illustrative example.
                </p>
              </div>
            </div>
          )}
        </div>
      </section>
      <RecordedRuns />
    </div>
  );
}
