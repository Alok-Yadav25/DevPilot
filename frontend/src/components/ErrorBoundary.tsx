import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { ArrowRight, RotateCcw } from "lucide-react";
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(_error: Error, _info: ErrorInfo) {}
  render() {
    return this.state.failed ? (
      <div className="page empty-state">
        <RotateCcw size={30} />
        <h1>The workspace hit a snag.</h1>
        <p>
          Reload to recover the page. Your saved run history remains in your
          browser or on your worker.
        </p>
        <button
          className="button button-primary"
          onClick={() => window.location.reload()}
        >
          Reload workspace
          <ArrowRight size={15} />
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
