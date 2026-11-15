import { expect, test } from "@playwright/test";
import { advanceSample, makeSample } from "../src/lib/examples";
function record() {
  let run = makeSample("slugify");
  for (let i = 0; i < 20; i++) run = advanceSample(run);
  return {
    ...run,
    id: "ui-test-recording",
    mode: "live",
    test_evidence: [
      {
        job_id: "ui-fixture",
        run_id: 42,
        status: "completed",
        url: "https://github.com/fixture/sandbox/actions/runs/42",
      },
    ],
  };
}
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    const data =
      url.pathname === "/api/health"
        ? {
            status: "setup_required",
            database: false,
            ready: false,
            runner: "replay",
            runner_healthy: true,
          }
        : url.pathname === "/api/replays"
          ? [
              {
                id: "ui-test-recording",
                repo_url: "https://github.com/examples/slugify",
                recorded_at: "2026-11-14T00:00:00Z",
                label: "Recorded real run",
              },
            ]
          : url.pathname === "/api/replays/ui-test-recording"
            ? {
                ...record(),
                mode: "replay",
                recorded_at: "2026-11-14T00:00:00Z",
              }
            : [];
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  });
});
test("overview form fits and has readable text without horizontal overflow", async ({
  page,
}, info) => {
  await page.goto("/workspace");
  const start = page.getByRole("button", { name: "Start run", exact: true });
  await expect(start).toBeVisible();
  const box = await start.boundingBox();
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      [...document.querySelectorAll("body *")]
        .filter(
          (e) =>
            e.getBoundingClientRect().width &&
            [...e.childNodes].some(
              (n) => n.nodeType === 3 && n.textContent?.trim(),
            ),
        )
        .filter((e) => parseFloat(getComputedStyle(e).fontSize) < 12)
        .map((e) => e.tagName),
    ),
  ).toEqual([]);
  await page.screenshot({
    path: info.outputPath("overview.png"),
    fullPage: true,
  });
});
test("illustrative run shows patch and requires explicit keyboard approval", async ({
  page,
}, info) => {
  await page.clock.install();
  const mutations: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST") mutations.push(req.url());
  });
  await page.goto("/workspace");
  await page
    .getByRole("button", { name: "Try an example", exact: true })
    .click();
  await page.getByRole("button", { name: /The wrong separator/ }).click();
  await expect(
    page.getByRole("button", { name: /Approve patch/ }),
  ).toBeDisabled();
  await expect(page.getByRole("tab", { name: "Workflow" })).toBeVisible();
  await page.clock.runFor(22000);
  await expect(
    page.getByRole("button", { name: /Approve patch/ }),
  ).toBeEnabled();
  await expect(
    page.getByRole("tab", { name: "Diff", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toContainText("slugify.py");
  await page.getByRole("tab", { name: "Workflow", exact: true }).click();
  await expect(page.locator(".react-flow")).toBeVisible();
  await page.getByRole("tab", { name: "Diff", exact: true }).click();
  await page.getByRole("button", { name: /Approve patch/ }).focus();
  await page.keyboard.press("a");
  const confirm = page.getByRole("button", {
    name: "Confirm approval",
    exact: true,
  });
  await expect(confirm).toBeVisible();
  await confirm.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Timeline", exact: true }).click();
  await expect(page.getByText("9/9", { exact: true })).toBeVisible();
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Workspace", exact: true }).click();
  await page.screenshot({
    path: info.outputPath("review.png"),
    fullPage: true,
  });
});
test("recorded replay keeps evidence and never dispatches a provider action", async ({
  page,
}) => {
  await page.clock.install();
  const mutations: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST") mutations.push(req.url());
  });
  await page.goto("/workspace");
  await page.getByRole("button", { name: /examples\/slugify.*Replay/ }).click();
  await expect(
    page.getByText("Recorded real run.", { exact: true }),
  ).toBeVisible();
  await page.clock.runFor(60000);
  await expect(
    page.getByRole("button", { name: /Approve patch/ }),
  ).toBeEnabled();
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Review checklist" }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Reject/ }).click();
  await page
    .getByRole("button", { name: "Confirm rejection", exact: true })
    .click();
  await expect(page.getByText("Rejected", { exact: true })).toBeVisible();
  expect(mutations).toEqual([]);
});

test("navigation, theme and connection errors stay usable", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/workspace");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  async function navigation() {
    if (info.project.name === "mobile")
      await page.getByRole("button", { name: "Open navigation" }).click();
  }
  await navigation();
  await page.getByRole("link", { name: "History", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "History", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("/");
  await expect(
    page.getByRole("textbox", { name: "Search runs" }),
  ).toBeFocused();
  await page.getByRole("textbox", { name: "Search runs" }).fill("no-match");
  await expect(
    page.getByRole("heading", { name: "No runs match this view" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reset filters" }).click();
  await navigation();
  await page.getByRole("link", { name: "Evaluation", exact: true }).click();
  await expect(
    page.getByText("No live results yet", { exact: true }),
  ).toBeVisible();
  await navigation();
  await page.getByRole("link", { name: "How it works", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "How it works", exact: true }),
  ).toBeVisible();
  await page.getByText("Requirements & limits", { exact: true }).click();
  await expect(
    page.getByText(/Actions dependency preparation uses public downloads/),
  ).toBeVisible();
  await navigation();
  await page.getByRole("button", { name: "Replay mode", exact: true }).click();
  await page
    .getByRole("textbox", { name: "API address" })
    .fill("https://invalid-worker.example");
  await page.getByLabel("Worker access token").fill("fake-worker-credential");
  await page.route("https://invalid-worker.example/api/**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "Invalid worker token. Check your settings.",
      }),
    }),
  );
  await page.getByRole("button", { name: "Test & save" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "Invalid worker token. Check your settings.",
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    await page.evaluate(
      () =>
        JSON.parse(localStorage.getItem("devpilot-workspace-v1")!).state.apiUrl,
    ),
  ).toBe("");
  expect(errors).toEqual([]);
  await page.screenshot({
    path: info.outputPath("about-light.png"),
    fullPage: true,
  });
});

test("worker errors do not masquerade as empty history or evaluation results", async ({
  page,
}, info) => {
  await page.addInitScript(() =>
    sessionStorage.setItem("devpilot-api-token", "fake-worker-credential"),
  );
  await page.route("**/api/health", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ready: true,
        database: true,
        runner: "github_actions",
      }),
    }),
  );
  for (const path of ["runs", "eval"]) {
    await page.route(`**/api/${path}`, (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Database temporarily unavailable." }),
      }),
    );
  }
  await page.goto("/runs");
  await expect(page.getByRole("alert")).toContainText(
    "Worker history unavailable",
  );
  await expect(
    page.getByRole("heading", { name: "No runs yet", exact: true }),
  ).toHaveCount(0);
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Evaluation", exact: true }).click();
  await expect(
    page.getByText("Results unavailable", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Export results" }),
  ).toBeDisabled();
});

test("mobile navigation supports Escape and keeps hidden links out of focus", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "mobile", "Mobile drawer interaction");
  await page.goto("/workspace");
  const menu = page.getByRole("button", { name: "Open navigation" });
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).not.toBeVisible();
  await menu.click();
  await expect(page.getByRole("link", { name: "DevPilot home" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.getByRole("button", { name: /Shortcuts/ })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "DevPilot home" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
});
