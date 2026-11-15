import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Run } from "./types";
import { advanceRecorded, makeRecorded } from "./replay";
import { advanceSample, makeSample } from "./examples";
type UIStore = {
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
      setApiUrl: (v) => set({ apiUrl: v.replace(/\/$/, "") }),
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
      partialize: (s) => ({
        theme: s.theme,
        apiUrl: s.apiUrl,
        samples: s.samples,
      }),
    },
  ),
);
export const getToken = () =>
  sessionStorage.getItem("devpilot-api-token") ?? "";
export const setToken = (v: string) =>
  v
    ? sessionStorage.setItem("devpilot-api-token", v)
    : sessionStorage.removeItem("devpilot-api-token");
