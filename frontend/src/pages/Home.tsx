import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  AnimatePresence,
  MotionConfig,
  motion,
  useReducedMotion,
} from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCheck,
  Code2,
  FileCode2,
  GitBranch,
  Github,
  GitPullRequest,
  LockKeyhole,
  Moon,
  Pause,
  Play,
  ScanLine,
  ShieldCheck,
  Sun,
  Terminal,
} from "lucide-react";
import { Logo, CreatorCredit } from "../components/Brand";
import { useUI } from "../lib/store";
import "../styles/landing.css";
const stages = ["Investigate", "Patch", "Review"];
const reveal = {
  hidden: { opacity: 0, y: 18 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: "easeOut" as const },
  },
};
const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12 } },
};
function PatchPreview() {
  const reduced = useReducedMotion();
  const [stage, setStage] = useState(1);
  const [playing, setPlaying] = useState(true);
  useEffect(() => {
    if (!playing || reduced) return;
    const timer = setInterval(() => {
      if (!document.hidden) setStage((value) => (value + 1) % stages.length);
    }, 4500);
    return () => clearInterval(timer);
  }, [playing, reduced]);
  return (
    <div className="hero-visual">
      <div className="orbit orbit-outer" aria-hidden="true" />
      <div className="orbit orbit-inner" aria-hidden="true" />
      <div className="visual-caption">
        <span className="tiny-cross" aria-hidden="true">
          +
        </span>{" "}
        A LITTLE LESS DEBUGGING. A LOT MORE FLOW.
      </div>
      <div className="patch-preview">
        <div className="preview-top">
          <span className="window-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            <Github size={13} /> examples / slugify
          </span>
          <span className="preview-sample">Illustrative preview</span>
        </div>
        <div className="preview-navigation">
          <div
            role="tablist"
            aria-label="Product preview"
            onKeyDown={(event) => {
              if (
                !["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)
              )
                return;
              event.preventDefault();
              const next =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? 2
                    : (stage + (event.key === "ArrowRight" ? 1 : 2)) % 3;
              setStage(next);
              setPlaying(false);
              event.currentTarget
                .querySelectorAll<HTMLButtonElement>('[role="tab"]')
                [next]?.focus();
            }}
          >
            {stages.map((name, index) => (
              <button
                key={name}
                id={`preview-tab-${index}`}
                role="tab"
                tabIndex={stage === index ? 0 : -1}
                aria-selected={stage === index}
                aria-controls="preview-panel"
                onClick={() => {
                  setStage(index);
                  setPlaying(false);
                }}
              >
                {name}
              </button>
            ))}
          </div>
          <button
            className="preview-play"
            onClick={() => setPlaying((value) => !value)}
            disabled={!!reduced}
            aria-label={playing && !reduced ? "Pause preview" : "Play preview"}
          >
            {playing && !reduced ? <Pause size={14} /> : <Play size={14} />}
          </button>
        </div>
        <div
          className="preview-panel"
          id="preview-panel"
          role="tabpanel"
          aria-labelledby={`preview-tab-${stage}`}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={stage}
              initial={reduced ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
            >
              {stage === 0 ? (
                <div className="investigation-preview">
                  <div className="preview-file">
                    <Terminal size={14} /> pytest · baseline
                  </div>
                  <div className="trace-line">
                    <span className="trace-number">01</span>
                    <span>
                      <Check size={13} /> Reproduced the same failure twice
                    </span>
                  </div>
                  <div className="trace-error">
                    <span>AssertionError</span>
                    <code>'hello_world' != 'hello-world'</code>
                  </div>
                  <div className="trace-line">
                    <span className="trace-number">02</span>
                    <span>
                      <ScanLine size={14} /> Located slugify.py:5
                    </span>
                  </div>
                  <p className="preview-hypothesis">
                    The words are correct.
                    <br />
                    The separator isn’t.
                  </p>
                </div>
              ) : stage === 1 ? (
                <div className="code-preview">
                  <div className="preview-file">
                    <FileCode2 size={14} /> slugify.py{" "}
                    <span>
                      +1 <em>−1</em>
                    </span>
                  </div>
                  <div className="code-lines">
                    <div>
                      <span>4</span>
                      <code>
                        <b>def</b> slugify(text: <i>str</i>):
                      </code>
                    </div>
                    <div className="code-removed">
                      <span>−</span>
                      <code>
                        {" "}
                        return <em>"_"</em>.join(words)
                      </code>
                    </div>
                    <div className="code-added">
                      <span>+</span>
                      <code>
                        {" "}
                        return <em>"-"</em>.join(words)
                      </code>
                    </div>
                    <div>
                      <span>6</span>
                      <code> </code>
                    </div>
                  </div>
                  <div className="preview-test">
                    <CheckCheck size={16} />
                    <span>
                      2 tests passed<span>Illustrative sample outcome</span>
                    </span>
                    <span className="test-duration">pytest</span>
                  </div>
                </div>
              ) : (
                <div className="review-preview">
                  <div className="preview-file">
                    <GitPullRequest size={14} /> Ready for your review
                  </div>
                  <h3>One line. The right separator.</h3>
                  <p>
                    Preserves whitespace handling.
                    <br />
                    Test files stay untouched.
                  </p>
                  <div className="preview-review-check">
                    <ShieldCheck size={17} />
                    <span>Your approval comes first.</span>
                    <LockKeyhole size={14} />
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
        <div className="preview-bottom">
          <span>
            <span className="preview-status-dot" />
            {stage === 0
              ? "Tracing the root cause"
              : stage === 1
                ? "Small patch. Tests preserved."
                : "Waiting for a human decision"}
          </span>
          <span>Python 3.11</span>
        </div>
      </div>
      <div className="floating-approval">
        <span className="approval-symbol">
          <img src="/devpilot-mark.svg" width="23" height="21" alt="" />
        </span>
        <span>
          Autonomous effort.<strong>Human control.</strong>
        </span>
        <Check size={16} />
      </div>
      <div className="visual-coordinate" aria-hidden="true">
        DP—01 <span>BUILT TO BE REVIEWED</span>
      </div>
    </div>
  );
}
export default function Home() {
  const navigate = useNavigate();
  const { theme, setTheme, startSample } = useUI();
  const reduced = useReducedMotion();
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  function demo() {
    navigate(`/run/${startSample("slugify")}`);
  }
  return (
    <MotionConfig reducedMotion="user">
      <div className="landing">
        <a className="skip-link" href="#landing-main">
          Skip to content
        </a>
        <header className="landing-header landing-container">
          <Link to="/" aria-label="DevPilot home">
            <Logo />
          </Link>
          <nav aria-label="Landing navigation">
            <a href="#product">Product</a>
            <a href="#workflow">How it works</a>
            <Link to="/evaluation">Evaluation</Link>
          </nav>
          <div className="landing-header-actions">
            <button
              className="landing-theme"
              onClick={setTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link className="header-workspace" to="/workspace">
              Workspace <ArrowUpRight size={16} />
            </Link>
          </div>
        </header>
        <main id="landing-main" tabIndex={-1}>
          <section
            className="landing-hero landing-container"
            aria-labelledby="hero-title"
          >
            <motion.div
              className="landing-hero-copy"
              initial={reduced ? false : "hidden"}
              animate="visible"
              variants={stagger}
            >
              <motion.div variants={reveal} className="hero-eyebrow">
                <span />
                YOUR AI ENGINEERING COPILOT
              </motion.div>
              <h1 id="hero-title">
                <motion.span variants={reveal}>Less firefighting.</motion.span>
                <motion.span variants={reveal}>
                  More <em>building.</em>
                </motion.span>
              </h1>
              <motion.p variants={reveal} className="hero-description">
                Turn a bug report into a patch you can review.
                <br className="desktop-break" /> DevPilot investigates, writes a
                focused fix, and runs the tests. You make the final call.
              </motion.p>
              <motion.div variants={reveal} className="landing-hero-actions">
                <Link className="landing-cta" to="/workspace">
                  Open workspace <ArrowUpRight size={18} />
                </Link>
                <button className="landing-demo" onClick={demo}>
                  <span>
                    <Play size={12} fill="currentColor" />
                  </span>
                  Try the demo
                </button>
              </motion.div>
              <motion.div variants={reveal} className="hero-footnote">
                <ShieldCheck size={14} />
                <span>No auto-merge. Always your decision.</span>
              </motion.div>
            </motion.div>
            <motion.div
              className="hero-visual-wrap"
              initial={reduced ? false : { opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.25 }}
            >
              <PatchPreview />
            </motion.div>
            <a
              href="#product"
              className="hero-scroll"
              aria-label="Explore DevPilot"
            >
              <ArrowDown size={15} />
              <span>BUILT FOR THE WAY YOU SHIP</span>
            </a>
          </section>
          <div className="technology-strip landing-container">
            <span>Fits your workflow.</span>
            <div>
              <Github size={19} /> GitHub
            </div>
            <div>
              <Code2 size={20} /> Python
            </div>
            <div>
              <CheckCheck size={20} /> pytest
            </div>
            <div className="groq-wordmark">
              Groq<span>Inference</span>
            </div>
            <span className="tech-end">Fewer handoffs. More momentum.</span>
          </div>
          <section
            className="product-section landing-container"
            id="product"
            aria-labelledby="product-title"
          >
            <motion.div
              className="section-intro"
              initial={reduced ? false : "hidden"}
              whileInView="visible"
              viewport={{ once: true, amount: 0.3 }}
              variants={reveal}
              transition={{ duration: 0.55 }}
            >
              <div>
                <span className="landing-kicker">01 / MEET YOUR COPILOT</span>
                <h2 id="product-title">
                  The heavy lifting.
                  <br />
                  <em>Handled.</em>
                </h2>
              </div>
              <p>
                Less time chasing stack traces.
                <br />
                More space for the work you actually
                <br className="desktop-break" /> want to do.
              </p>
            </motion.div>
            <div className="capability-grid">
              {[
                {
                  Icon: ScanLine,
                  title: "Find the why.",
                  description:
                    "Reproduce the failure. Trace the relevant code. Follow a clear hypothesis, not a blind guess.",
                  number: "01",
                },
                {
                  Icon: GitBranch,
                  title: "Keep the fix focused.",
                  description:
                    "Small source changes. Protected test files. Bounded retries when the first patch needs work.",
                  number: "02",
                },
                {
                  Icon: GitPullRequest,
                  title: "Own the final call.",
                  description:
                    "See the diff, test evidence and risks. Approve before a target branch or draft PR is created.",
                  number: "03",
                },
              ].map(({ Icon, title, description, number }, index) => (
                <motion.article
                  key={number}
                  initial={reduced ? false : { opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.4 }}
                  transition={{ duration: 0.5, delay: index * 0.08 }}
                >
                  <div className="capability-top">
                    <Icon size={24} strokeWidth={1.3} />
                    <span>{number}</span>
                  </div>
                  <h3>{title}</h3>
                  <p>{description}</p>
                </motion.article>
              ))}
            </div>
          </section>
          <section
            className="workflow-section landing-container"
            id="workflow"
            aria-labelledby="workflow-title"
          >
            <div className="workflow-editorial">
              <span className="landing-kicker">
                02 / LESS FRICTION. MORE FLOW.
              </span>
              <h2 id="workflow-title">
                From “it’s broken”
                <br />
                to <em>“here’s the fix.”</em>
              </h2>
              <p>
                One transparent workspace.
                <br />
                Every step in the open.
              </p>
              <Link to="/about" className="landing-text-link">
                See how it works <ArrowUpRight size={16} />
              </Link>
            </div>
            <ol className="landing-process">
              {[
                [
                  "Bring the bug.",
                  "Add a public Python repo and a reproducible pytest failure.",
                ],
                [
                  "Follow the investigation.",
                  "Watch the agent locate, patch and test. Inspect every attempt.",
                ],
                [
                  "Review. Then decide.",
                  "Check the evidence. Keep it as a dry run, or approve a draft PR.",
                ],
              ].map(([title, description], index) => (
                <li key={title}>
                  <span className="process-index">0{index + 1}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </div>
                  {index === 2 && <Check size={18} />}
                </li>
              ))}
            </ol>
          </section>
          <section className="landing-final landing-container">
            <div className="final-inner">
              <div>
                <span className="landing-kicker">
                  YOUR NEXT FIX STARTS HERE
                </span>
                <h2>
                  Build more.
                  <br />
                  <em>Chase less.</em>
                </h2>
              </div>
              <div className="final-action">
                <Link className="landing-cta" to="/workspace">
                  Open workspace <ArrowUpRight size={19} />
                </Link>
                <p>Python + pytest. Dry runs by default.</p>
                <button onClick={demo}>
                  Just exploring? Try an illustrative demo{" "}
                  <ArrowRight size={14} />
                </button>
              </div>
              <img
                className="final-watermark"
                src="/devpilot-mark.svg"
                alt=""
                width="280"
                height="250"
              />
            </div>
          </section>
        </main>
        <footer className="landing-footer landing-container">
          <Link to="/" aria-label="DevPilot home">
            <Logo />
          </Link>
          <span className="footer-note">Autonomous effort. Human control.</span>
          <CreatorCredit />
        </footer>
      </div>
    </MotionConfig>
  );
}
