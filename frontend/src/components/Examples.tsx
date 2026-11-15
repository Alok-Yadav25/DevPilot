import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Braces,
  TextCursorInput,
  Timer,
} from "lucide-react";
import { EXAMPLES } from "../lib/examples";
import { useUI } from "../lib/store";
export function ExampleCards({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate();
  const start = useUI((s) => s.startSample);
  const icons = [TextCursorInput, Braces, Timer];
  return (
    <div className={`example-grid ${compact ? "example-compact" : ""}`}>
      {EXAMPLES.map((example, i) => {
        const Icon = icons[i];
        return (
          <button
            key={example.id}
            className="example-card"
            onClick={() => navigate(`/run/${start(example.id)}`)}
          >
            <div className="example-card-top">
              <span className={`example-icon example-icon-${i}`}>
                <Icon size={20} />
              </span>
              <span className="tag">Illustrative sample</span>
              <ArrowUpRight size={15} className="example-arrow" />
            </div>
            <h3>{example.name}</h3>
            <p>{example.description}</p>
            <div className="example-card-bottom">
              <span>
                <span className="python-dot" />
                {example.repo}
                <span className="muted">/ Python</span>
              </span>
              <span>
                Try example
                <ArrowRight size={13} />
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
