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
  await page.goto("/");
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
  await page.goto("/");
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
  await page.goto("/");
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
