import {
  ArrowRight,
  Box,
  Eye,
  FileCode2,
  GitBranch,
  GitPullRequest,
  HeartHandshake,
  LockKeyhole,
  Network,
  ShieldCheck,
  Timer,
  WandSparkles,
  Zap,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
export default function About() {
  const navigate = useNavigate();
  return (
    <div className="page about-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">AUTONOMOUS, WITH GUARDRAILS</div>
          <h1>
            An engineer that shows its work
            <span className="heading-dot">.</span>
          </h1>
          <p>
            Small fixes, real test evidence, and a human at the finish line.
          </p>
        </div>
        <Button onClick={() => navigate("/new")}>
          Start a run
          <ArrowRight size={15} />
        </Button>
      </div>
      <section className="about-intro panel">
        <div>
          <span className="hero-tag">
            <Zap size={13} />
            BUILT FOR PYTHON. BUILT FOR TRUST.
          </span>
          <h2>
            From “why is this failing?”
            <br />
            to “here’s the fix.”
          </h2>
          <p>
            DevPilot is a focused software engineering agent for Python
            repositories using pytest. It investigates an existing failure,
            proposes a small patch, and tests it in isolation. You get the diff
            and the evidence before target changes are pushed.
          </p>
        </div>
        <div className="about-flow">
          {[
            {
              icon: GithubIcon,
              label: "Your repository",
              sub: "Bug description + failing test",
            },
            {
              icon: WandSparkles,
              label: "DevPilot agent",
              sub: "Locate → diagnose → patch",
            },
            {
              icon: Box,
              label: "Isolated test runner",
              sub: "Tests offline. Enforced limits.",
            },
            {
              icon: HeartHandshake,
              label: "Your approval",
              sub: "The final decision is yours",
            },
          ].map(({ icon: Icon, label, sub }, i) => (
            <div key={label}>
              <span className={`about-flow-icon flow-icon-${i}`}>
                <Icon size={21} />
              </span>
              <div>
                <strong>{label}</strong>
                <p>{sub}</p>
              </div>
              {i < 3 && <span className="flow-line" />}
            </div>
          ))}
        </div>
      </section>
      <div className="section-heading">
        <div>
          <h2>Safety is part of the architecture</h2>
          <p>
            These are runtime boundaries, not just instructions in a prompt.
          </p>
        </div>
      </div>
      <div className="safety-grid">
        {[
          {
            icon: Network,
            title: "A truly isolated workspace",
            text: "Tests run as a non-root user with networking disabled, a read-only root filesystem, resource limits and no host mounts. Actions dependency preparation uses public downloads before test networking is disabled.",
          },
          {
            icon: LockKeyhole,
            title: "Credentials stay outside",
            text: "GitHub and Groq keys live on your backend. They never enter the sandbox, the repository, or the model’s source context.",
          },
          {
            icon: Timer,
            title: "Every run has an endpoint",
            text: "A maximum of three patch attempts. Repeated errors stop the loop. Each test run has a hard 120-second limit and resource caps.",
          },
          {
            icon: FileCode2,
            title: "The tests are off-limits",
            text: "The validator rejects test changes, unsafe paths, whole-file replacements, and oversized patches before the code is tested.",
          },
          {
            icon: Eye,
            title: "Evidence you can inspect",
            text: "See the selected files, concise hypothesis, attempted diffs, test outcomes, stop reasons, and the final risk review.",
          },
          {
            icon: GitPullRequest,
            title: "Your approval comes first",
            text: "Live publication requires an explicit approval tied to the reviewed diff. DevPilot creates a branch and a draft PR. It never merges.",
          },
        ].map(({ icon: Icon, title, text }) => (
          <article className="panel safety-card" key={title}>
            <span>
              <Icon size={20} />
            </span>
            <h3>{title}</h3>
            <p>{text}</p>
          </article>
        ))}
      </div>
      <section className="limitations panel">
        <div>
          <ShieldCheck size={23} />
          <h2>
            Practical by design.
            <br />
            Honest about its limits.
          </h2>
        </div>
        <div>
          <p>
            Passing tests don’t prove a patch is correct, and a container shares
            its host’s kernel. Review every change and use a separate public
            GitHub Actions sandbox repository for test execution.
          </p>
          <p>
            Actions prepares dependencies with public downloads, then
            disconnects test networking. The local container runner instead
            requires a trusted offline image or wheelhouse. Missing dependencies
            and network-dependent tests stop with an explanation.
          </p>
          <p>
            The default Actions runner needs no local container daemon. Keep
            provider credentials on the backend, using environment variables;
            the website can still offer clearly labeled sample walkthroughs when
            it’s offline.
          </p>
        </div>
      </section>
      <div className="about-bottom">
        <span className="brand-mark">
          <Zap size={23} fill="currentColor" />
        </span>
        <h2>
          Less time chasing bugs.
          <br />
          More time building what’s next.
        </h2>
        <Button onClick={() => navigate("/new")}>
          Give your agent a mission
          <ArrowRight size={16} />
        </Button>
        <small>No billing. No trackers. No auto-merge.</small>
      </div>
    </div>
  );
}
function GithubIcon({ size = 20 }: { size?: number }) {
  return <GitBranch size={size} />;
}
