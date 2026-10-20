import type { Adapter } from "./contracts";
import { realAdapter } from "./real";
export const isDemo =
  import.meta.env.DEV &&
  (import.meta.env.MODE === "demo" || import.meta.env.VITE_APP_MODE === "demo");
export const api: Adapter = isDemo
  ? (await import("./demo")).demoAdapter
  : realAdapter;
