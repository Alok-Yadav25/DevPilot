import { parseDiff } from "react-diff-view";
/** Preserve paths and each file boundary for timestamp-free git-apply diffs. */
export function parsePatch(diff: string) {
  const gitDiff = diff.replace(
    /^--- a\/([^\n]+)\n\+\+\+ b\/([^\n]+)\n/gm,
    (_, oldPath: string, newPath: string) =>
      `diff --git a/${oldPath} b/${newPath}\n--- a/${oldPath}\n+++ b/${newPath}\n`,
  );
  return parseDiff(gitDiff);
}
