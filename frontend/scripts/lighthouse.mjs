// Local frontend measurement: production build + clearly mocked API.
import { createServer } from "node:http";
import {
  access,
  readFile,
  stat,
  mkdir,
  mkdtemp,
  rm,
  writeFile,
} from "node:fs/promises";
import { resolve, extname } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import ts from "typescript";
const root = resolve("dist"),
  output = resolve(
    process.env.DEVPILOT_QUALITY_OUTPUT || "../docs/quality/lighthouse",
  );
await mkdir(output, { recursive: true });
const mime = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://localhost");
    if (url.pathname.startsWith("/api/")) {
      res.setHeader("Content-Type", "application/json");
      res.end(
        JSON.stringify(
          url.pathname === "/api/health"
            ? {
                status: "setup_required",
                database: false,
                ready: false,
                runner: "replay",
                runner_healthy: true,
              }
            : [],
        ),
      );
      return;
    }
    let file = resolve(root, "." + decodeURIComponent(url.pathname));
    if (!file.startsWith(root + "/")) file = resolve(root, "index.html");
    try {
      if (!(await stat(file)).isFile()) file = resolve(root, "index.html");
    } catch {
      file = resolve(root, "index.html");
    }
    res.setHeader(
      "Content-Type",
      mime[extname(file)] ?? "application/octet-stream",
    );
    res.end(await readFile(file));
  } catch {
    res.statusCode = 500;
    res.end("Local quality server error");
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;
const profile = await mkdtemp(resolve(tmpdir(), "devpilot-quality-"));
let context;
try {
  const modulePath =
    process.env.DEVPILOT_LIGHTHOUSE_MODULE ||
    resolve("../.devpilot/quality-tools/node_modules/lighthouse/core/index.js");
  await access(modulePath).catch(() => {
    throw new Error(
      "Install the optional Lighthouse tool into .devpilot/quality-tools first; see frontend/README.md.",
    );
  });
  const { default: lighthouse } = await import(
    modulePath ? pathToFileURL(resolve(modulePath)).href : "lighthouse"
  );
  const { default: desktop } = await import(
    modulePath
      ? pathToFileURL(resolve(modulePath, "../config/desktop-config.js")).href
      : "lighthouse/core/config/desktop-config.js"
  );
  const source = await readFile("src/lib/examples.ts", "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const examples = await import(
    "data:text/javascript;base64," + Buffer.from(compiled).toString("base64")
  );
  let sample = examples.makeSample("slugify");
  for (let i = 0; i < 20; i++) sample = examples.advanceSample(sample);
  sample.id = "sample-quality";
  context = await chromium.launchPersistentContext(profile, {
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    args: ["--remote-debugging-port=9333"],
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = context.pages()[0];
  await page.goto(base);
  await page.evaluate(
    (sample) =>
      localStorage.setItem(
        "devpilot-workspace-v1",
        JSON.stringify({
          state: { theme: "dark", apiUrl: "", samples: [sample] },
          version: 0,
        }),
      ),
    sample,
  );
  const summaries = [];
  for (let trial = 1; trial <= 3; trial++) {
    for (const [name, path] of [
      ["overview", "/"],
      ["live-run", "/run/sample-quality"],
      ["history", "/runs"],
    ]) {
      const result = await lighthouse(
        base + path,
        {
          port: 9333,
          output: "json",
          logLevel: "error",
          onlyCategories: ["performance", "accessibility"],
          disableStorageReset: true,
        },
        desktop,
      );
      if (!result?.lhr || result.lhr.runtimeError)
        throw Error(
          JSON.stringify(result?.lhr?.runtimeError ?? "No audit result"),
        );
      await writeFile(
        resolve(output, `${name}-trial-${trial}.json`),
        JSON.stringify(result.lhr, null, 2) + "\n",
      );
      const failures = result.lhr.categories.accessibility.auditRefs
        .map((ref) => result.lhr.audits[ref.id])
        .filter((a) => a.score !== null && a.score < 1)
        .map((a) => ({ id: a.id, title: a.title, items: a.details?.items }));
      const row = {
        page: name,
        trial,
        performance: Math.round(result.lhr.categories.performance.score * 100),
        accessibility: Math.round(
          result.lhr.categories.accessibility.score * 100,
        ),
        lighthouse_version: result.lhr.lighthouseVersion,
        observed_at: result.lhr.fetchTime,
        failures,
      };
      summaries.push(row);
      console.log(JSON.stringify(row));
    }
  }
  const median = (values) => [...values].sort((a, b) => a - b)[1];
  const pages = ["overview", "live-run", "history"].map((page) => {
    const trials = summaries.filter((row) => row.page === page);
    return {
      page,
      performance_median: median(trials.map((row) => row.performance)),
      accessibility_median: median(trials.map((row) => row.accessibility)),
      trials,
    };
  });
  await writeFile(
    resolve(output, "summary.json"),
    JSON.stringify(
      {
        scope:
          "Local production build, Lighthouse 10.1.1 desktop preset, persistent warm profile, mocked API; live-run is an illustrative sample. Three trials retained; not a real repair or hosted/cold-start measurement.",
        results: pages,
      },
      null,
      2,
    ) + "\n",
  );
} finally {
  await context?.close();
  await new Promise((r) => server.close(r));
  await rm(profile, { recursive: true, force: true });
}
