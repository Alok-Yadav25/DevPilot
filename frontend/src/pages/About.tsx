import { Check, GitBranch, ShieldCheck, TestTube2 } from "lucide-react";
export default function About() {
  return (
    <div className="page about-page concise-about">
      <header className="page-heading">
        <div>
          <h1>How it works</h1>
          <p>Python bugs. Tested patches. Your approval.</p>
        </div>
      </header>
      <section className="process-steps" aria-label="Repair process">
        {[
          {
            icon: GitBranch,
            title: "1. Reproduce",
            text: "Clone the public repository and confirm the failure twice.",
          },
          {
            icon: TestTube2,
            title: "2. Patch & test",
            text: "Find the cause, make a small source edit and rerun pytest.",
          },
          {
            icon: Check,
            title: "3. Review",
            text: "Inspect the diff and test evidence. Approve or reject the patch.",
          },
        ].map(({ icon: Icon, title, text }) => (
          <article className="panel" key={title}>
            <Icon size={20} />
            <h2>{title}</h2>
            <p>{text}</p>
          </article>
        ))}
      </section>
      <section className="panel safety-summary">
        <h2>
          <ShieldCheck size={20} />
          You stay in control
        </h2>
        <ul>
          <li>Tests cannot be edited. Repairs stop after three attempts.</li>
          <li>
            Target branches and draft PRs require your approval. Nothing is
            merged.
          </li>
          <li>Dry runs create no target branch or PR.</li>
        </ul>
      </section>
      <details className="execution-details panel">
        <summary>Requirements & limits</summary>
        <p>
          Live runs require a configured worker, a public allowlisted Python
          3.11 repository and a reproducible pytest failure.
        </p>
        <p>
          Tests use a non-root container with resource limits and networking
          disabled. Actions dependency preparation uses public downloads; strict
          offline installation needs a prepared image or wheelhouse.
        </p>
        <p>
          Passing tests cannot prove a repair is correct. Inspect behavior and
          edge cases before approval. Real GitHub/Groq end-to-end verification
          is still pending.
        </p>
        <p>
          Illustrative examples are scripted. Recorded runs include their
          original evidence. Neither playback mode calls a model or publishes a
          PR.
        </p>
      </details>
    </div>
  );
}
