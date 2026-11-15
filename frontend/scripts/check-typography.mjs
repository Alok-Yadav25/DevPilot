import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
const files = (directory) =>
  readdirSync(directory, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? files(join(directory, entry.name))
      : [join(directory, entry.name)],
  );
const failures = [];
for (const file of files("src").filter((file) => /\.(css|tsx)$/.test(file))) {
  const source = readFileSync(file, "utf8");
  for (const match of source.matchAll(
    /font-size:\s*([\d.]+)(px|rem)|fontSize:\s*(\d+)|text-\[([\d.]+)px\]/g,
  )) {
    const size = match[1]
      ? Number(match[1]) * (match[2] === "rem" ? 16 : 1)
      : Number(match[3] ?? match[4]);
    if (size < 12)
      failures.push(
        `${file}:${source.slice(0, match.index).split("\n").length}: ${size}px`,
      );
  }
}
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("Typography check passed: no authored text sizes below 12px.");
