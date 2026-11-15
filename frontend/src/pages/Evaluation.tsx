import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CircleDashed,
  FlaskConical,
  Info,
  ShieldCheck,
  Target,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { useEvaluation } from "../lib/api";
import catalog from "../lib/evaluation-cases.json";
const categories = [
  "String handling",
  "Boundary conditions",
  "Off-by-one",
  "Collections",
  "Numeric logic",
];
export default function Evaluation() {
  const { data, isLoading } = useEvaluation();
  const [category, setCategory] = useState("All cases");
  const [status, setStatus] = useState("all");
  const cases =
    data?.results ??
    catalog.map((c) => ({
      ...c,
      repo: `synthetic/${c.id}`,
      status: "not_run",
      attempts: 0,
      duration_seconds: null,
    }));
  const filtered = cases.filter(
    (c) =>
      (category === "All cases" || category === c.category) &&
      (status === "all" || c.status === status),
  );
  function download() {
    const blob = new Blob(
      [
        JSON.stringify(
          data ?? {
            executed: 0,
            passed: 0,
            success_rate: null,
            results: cases,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "devpilot-evaluation.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">EVIDENCE OVER PROMISES</div>
          <h1>
            How good is the agent, really<span className="heading-dot">?</span>
          </h1>
          <p>Reproducible cases. Every attempt counted. Failures included.</p>
        </div>
        <Button variant="secondary" onClick={download}>
          <ArrowDownToLine size={15} />
          Export results
        </Button>
      </div>
      <div className="evaluation-note">
        <span className="evaluation-note-icon">
          <FlaskConical size={21} />
        </span>
        <div>
          <strong>No inflated benchmarks.</strong>
          <p>
            {data?.executed
              ? `${data.executed} real evaluation runs are recorded on your worker. Sample walkthroughs are excluded.`
              : "No live evaluation runs have been recorded yet. Walkthroughs and controller tests never count as autonomous repairs."}
          </p>
        </div>
        <span className="tag">TRANSPARENT BY DESIGN</span>
      </div>
      {!!data?.executed && (
        <div className="stat-grid evaluation-stats">
          {[
            {
              label: "Repair success",
              value: data?.success_rate != null ? `${data.success_rate}%` : "—",
              sub: "Passing repairs / completed cases",
              icon: Target,
            },
            {
              label: "Cases executed",
              value: `${data?.executed ?? 0} / ${data?.total_cases ?? 25}`,
              sub: "25 curated synthetic bug cases",
              icon: FlaskConical,
            },
            {
              label: "Average attempts",
              value: data?.average_attempts?.toFixed(1) ?? "—",
              sub: "Across all completed cases",
              icon: TrendingUp,
            },
            {
              label: "Failed cases",
              value: String(data?.failed ?? 0),
              sub: "Failures stay in the denominator",
              icon: ShieldCheck,
            },
          ].map(({ label, value, sub, icon: Icon }) => (
            <div className="stat-card" key={label}>
              <div className="stat-top">
                <span>{label}</span>
                <Icon size={17} className="muted" />
              </div>
              <div className="stat-value">{value}</div>
              <div className="stat-detail">{sub}</div>
            </div>
          ))}
        </div>
      )}
      <div className="section-heading">
        <div>
          <h2>The evaluation set</h2>
          <p>
            Focused Python bugs across five categories. Test files remain
            protected.
          </p>
        </div>
        <span className="muted small">Python 3.11 · pytest</span>
      </div>
      <div className="panel">
        <div className="table-toolbar">
          <div className="filter-tabs">
            {["All cases", ...categories].map((c) => (
              <button
                className={category === c ? "active" : ""}
                onClick={() => setCategory(c)}
                key={c}
              >
                {c}
              </button>
            ))}
          </div>
          <select
            aria-label="Filter evaluation status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="passed">Passed</option>
            <option value="failed">Failed</option>
            <option value="not_run">Not run</option>
          </select>
        </div>
        <div className="table-scroll">
          <div className="eval-table-head">
            <span>BUG CASE</span>
            <span>CATEGORY</span>
            <span>RESULT</span>
            <span>ATTEMPTS</span>
          </div>
          {isLoading ? (
            <div className="skeleton skeleton-card" />
          ) : filtered.length ? (
            filtered.map((item, i) => (
              <div key={item.id} className="eval-row">
                <div>
                  <span className="case-number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>
                    <strong>{item.name}</strong>
                    <small>{item.repo}</small>
                  </span>
                </div>
                <span className="muted">{item.category}</span>
                <span
                  className={`eval-result ${item.status === "passed" ? "text-success" : item.status === "failed" ? "text-error" : ""}`}
                >
                  {item.status === "not_run" ? (
                    <CircleDashed size={13} />
                  ) : (
                    <Check size={13} />
                  )}{" "}
                  {item.status === "not_run"
                    ? "Not run"
                    : item.status === "passed"
                      ? "Passed"
                      : "Failed"}
                </span>
                <span className="mono muted">{item.attempts || "—"}</span>
              </div>
            ))
          ) : (
            <div className="empty-state">
              <h3>No cases in this view</h3>
              <p>Try another category or result filter.</p>
            </div>
          )}
        </div>
        <div className="table-footer">
          <span>{filtered.length} cases</span>
          <span>Walkthroughs excluded · Results come from your worker</span>
        </div>
      </div>
      <div className="methodology panel">
        <span className="methodology-icon">
          <Info size={21} />
        </span>
        <div>
          <h3>What counts as a successful repair?</h3>
          <p>
            A real model-generated patch must pass the complete pytest suite in
            Docker, preserve the test inventory, and address the intended bug.
            Each report records the model, commit, attempts, diff, and test
            evidence. A human still reviews correctness.
          </p>
          <Link className="text-link" to="/about">
            Read about the safety model
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}
