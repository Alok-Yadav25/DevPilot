import { afterEach, expect, it, vi } from "vitest";

afterEach(() => {
  localStorage.clear();
  vi.unstubAllEnvs();
  vi.resetModules();
});

it.each([
  ["", "https://deployed.example"],
  ["https://custom.example", "https://custom.example"],
])("migrates the old saved API address %s", async (saved, expected) => {
  vi.stubEnv("VITE_API_URL", "https://deployed.example");
  localStorage.setItem(
    "devpilot-workspace-v1",
    JSON.stringify({
      state: { apiUrl: saved, theme: "light", samples: [] },
      version: 0,
    }),
  );
  const { useUI } = await import("./store");
  expect(useUI.getState().apiUrl).toBe(expected);
  expect(useUI.getState().theme).toBe("light");
});

it("keeps an explicitly saved proxy address after the migration", async () => {
  vi.stubEnv("VITE_API_URL", "https://deployed.example");
  localStorage.setItem(
    "devpilot-workspace-v1",
    JSON.stringify({ state: { apiUrl: "", samples: [] }, version: 1 }),
  );
  const { useUI } = await import("./store");
  expect(useUI.getState().apiUrl).toBe("");
});
