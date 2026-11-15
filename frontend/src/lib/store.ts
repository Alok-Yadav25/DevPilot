import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Run } from "./types";
import { advanceRecorded, makeRecorded } from "./replay";
import { advanceSample, makeSample } from "./examples";
type UIStore = {
  connectionRevision: number;
  connectionState: import("./client").ConnectionState;
  theme: "dark" | "light";
  setTheme: () => void;
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  connectionOpen: boolean;
  setConnectionOpen: (v: boolean) => void;
  shortcutsOpen: boolean;
  setShortcutsOpen: (v: boolean) => void;
  apiUrl: string;
  setApiUrl: (v: string) => void;
  samples: Run[];
  startSample: (id: string) => string;
  startRecorded: (record: Run) => string;
  updateSample: (id: string, values: Partial<Run>) => void;
  tick: () => void;
  clearSamples: () => void;
};
export const useUI = create<UIStore>()(
  persist(
    (set, get) => ({
      connectionRevision: 0,
      connectionState: "connected",
      theme: "dark",
      setTheme: () =>
        set((s) => ({ theme: s.theme === "dark" ? "light" : "dark" })),
      collapsed: false,
      setCollapsed: (v) => set({ collapsed: v }),
      connectionOpen: false,
      setConnectionOpen: (v) => set({ connectionOpen: v }),
      shortcutsOpen: false,
      setShortcutsOpen: (v) => set({ shortcutsOpen: v }),
      apiUrl: import.meta.env.VITE_API_URL ?? "",
      setApiUrl: (v) =>
        set((s) => ({
          apiUrl: v.replace(/\/$/, ""),
          connectionRevision: s.connectionRevision + 1,
        })),
      samples: [],
      startSample: (id) => {
        const run = makeSample(id);
        set((s) => ({ samples: [run, ...s.samples].slice(0, 30) }));
        return run.id;
      },
      startRecorded: (record) => {
        const run = makeRecorded(record);
        set((s) => ({ samples: [run, ...s.samples].slice(0, 30) }));
        return run.id;
      },
      updateSample: (id, values) =>
        set((s) => ({
          samples: s.samples.map((r) =>
            r.id === id
              ? {
                  ...r,
                  ...values,
                  ...(typeof values.paused === "boolean"
                    ? { playback_tick: Date.now() }
                    : {}),
                }
              : r,
          ),
        })),
      tick: () => {
        if (get().samples.some((r) => r.status === "running" && !r.paused))
          set((s) => ({
            samples: s.samples.map((r) =>
              r.mode === "replay" ? advanceRecorded(r) : advanceSample(r),
            ),
          }));
      },
      clearSamples: () => set({ samples: [] }),
    }),
    {
      name: "devpilot-workspace-v1",
      version: 1,
      migrate: (persisted) => {
        const saved = persisted as Partial<
          Pick<UIStore, "theme" | "apiUrl" | "samples">
        >;
        return {
          theme: saved.theme ?? "dark",
          samples: saved.samples ?? [],
          apiUrl: saved.apiUrl || import.meta.env.VITE_API_URL || "",
        };
      },
      partialize: (s) => ({
        theme: s.theme,
        apiUrl: s.apiUrl,
        samples: s.samples,
      }),
    },
  ),
);
export function getToken(): string {
  try {
    return sessionStorage.getItem("devpilot-api-token") ?? "";
  } catch {
    return "";
  }
}
function writeToken(value: string) {
  try {
    if (value) sessionStorage.setItem("devpilot-api-token", value);
    else sessionStorage.removeItem("devpilot-api-token");
  } catch {
    throw new Error("Allow session storage to save the worker connection.");
  }
}
export function setToken(value: string) {
  writeToken(value);
  useUI.setState((s) => ({ connectionRevision: s.connectionRevision + 1 }));
}
export function saveConnection(url: string, token: string) {
  writeToken(token);
  useUI.setState((s) => ({
    apiUrl: url,
    connectionRevision: s.connectionRevision + 1,
    connectionState: "connected",
  }));
}
