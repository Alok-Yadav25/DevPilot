import { Diff, Hunk } from "react-diff-view";
import "react-diff-view/style/index.css";
import { FileCode2 } from "lucide-react";
import { parsePatch } from "../lib/diff";
export default function PatchViewer({ diff }: { diff: string }) {
  try {
    const files = parsePatch(diff);
    if (!files.length) return <pre className="raw-patch">{diff}</pre>;
    return (
      <div className="diff-view">
        {files.map((file) => (
          <div key={file.newPath}>
            <div className="diff-file-title">
              <FileCode2 size={14} />
              {file.newPath}
              <span>
                <i>
                  +
                  {file.hunks.reduce(
                    (n, h) =>
                      n + h.changes.filter((c) => c.type === "insert").length,
                    0,
                  )}
                </i>
                <b>
                  −
                  {file.hunks.reduce(
                    (n, h) =>
                      n + h.changes.filter((c) => c.type === "delete").length,
                    0,
                  )}
                </b>
              </span>
            </div>
            <div className="diff-table-scroll">
              <Diff viewType="unified" diffType={file.type} hunks={file.hunks}>
                {(hunks) =>
                  hunks.map((hunk) => <Hunk key={hunk.content} hunk={hunk} />)
                }
              </Diff>
            </div>
          </div>
        ))}
      </div>
    );
  } catch {
    return <pre className="raw-patch">{diff}</pre>;
  }
}
