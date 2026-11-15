import { expect, test } from "@playwright/test";

test("landing has a sharp logo, usable hero, accessible preview and creator credit", async ({
  page,
}, info) => {
  const errors: string[] = [],
    apiCalls: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiCalls.push(request.url());
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Less firefighting. More building." }),
  ).toBeVisible();
  const cta = page.getByRole("link", { name: "Open workspace" }).first();
  const box = await cta.boundingBox();
  expect(box!.y + box!.height).toBeLessThan(page.viewportSize()!.height);
  expect(
    await page
      .locator(".brand-symbol")
      .first()
      .evaluate(
        (image: HTMLImageElement) => image.complete && image.naturalWidth > 0,
      ),
  ).toBe(true);
  await expect(
    page.getByRole("tab", { name: "Patch", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Review", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Your approval comes first.",
  );
  await page.getByRole("tab", { name: "Review", exact: true }).focus();
  await page.keyboard.press("Home");
  await expect(page.getByRole("tab", { name: "Investigate" })).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText("AssertionError");
  await page.getByRole("tab", { name: "Patch", exact: true }).click();
  await expect(page.getByRole("link", { name: /Alok Yadav/ })).toHaveAttribute(
    "href",
    "https://github.com/Alok-Yadav25",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() =>
      [...document.querySelectorAll("body *")]
        .filter(
          (element) =>
            element.getBoundingClientRect().width &&
            [...element.childNodes].some(
              (node) => node.nodeType === 3 && node.textContent?.trim(),
            ),
        )
        .filter(
          (element) => parseFloat(getComputedStyle(element).fontSize) < 12,
        )
        .map((element) => element.className),
    ),
  ).toEqual([]);
  expect(errors).toEqual([]);
  expect(apiCalls).toEqual([]);
  await page.locator(".landing-final").scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("heading", { name: "Build more. Chase less." }),
  ).toBeVisible();
  await page
    .locator(".landing-final")
    .screenshot({ path: info.outputPath("landing-final.png") });
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("landing-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.screenshot({
    path: info.outputPath("landing-light.png"),
    fullPage: true,
  });
  if (info.project.name === "mobile") {
    await page.setViewportSize({ width: 320, height: 740 });
    const headerLink = await page.locator(".header-workspace").boundingBox();
    expect(headerLink!.x + headerLink!.width).toBeLessThanOrEqual(320);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await cta.click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(
    page.getByRole("button", { name: "Start run", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Alok Yadav/ })).toHaveAttribute(
    "href",
    "https://github.com/Alok-Yadav25",
  );
});

test("landing demo works without a worker and cannot publish", async ({
  page,
}) => {
  const mutations: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") mutations.push(request.url());
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Try the demo", exact: true }).click();
  await expect(page).toHaveURL(/\/run\/sample-/);
  await expect(
    page.getByText("Illustrative sample.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Approve patch/ }),
  ).toBeDisabled();
  expect(mutations).toEqual([]);
});

test("reduced motion keeps the preview still", async ({ page }) => {
  await page.clock.install();
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Play preview" }),
  ).toBeDisabled();
  await page.clock.runFor(14000);
  await expect(
    page.getByRole("tab", { name: "Patch", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  expect(
    await page
      .locator(".floating-approval")
      .evaluate((element) => getComputedStyle(element).animationName),
  ).toBe("none");
});

test("animated preview advances and can be paused", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.clock.install();
  await page.goto("/");
  await page.clock.runFor(5000);
  await expect(
    page.getByRole("tab", { name: "Review", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: "Pause preview" }).click();
  await page.clock.runFor(10000);
  await expect(
    page.getByRole("tab", { name: "Review", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("button", { name: "Play preview" }),
  ).toBeEnabled();
});

test("hero text becomes visible with motion enabled", async ({
  page,
}, info) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  // Real browser time verifies compositor animations; fake timers cover autoplay separately.
  await expect(page.locator("#hero-title > span").first()).toHaveCSS(
    "opacity",
    "1",
  );
  await expect(page.locator("#hero-title > span").last()).toHaveCSS(
    "opacity",
    "1",
  );
  await page
    .locator(".landing-hero")
    .screenshot({ path: info.outputPath("hero-motion.png") });
});
