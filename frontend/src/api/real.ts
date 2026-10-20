import { z } from "zod";
import {
  sessionSchema,
  policySchema,
  conversationSchema,
  claimSchema,
  comparisonSchema,
  configSchema,
  type Adapter,
} from "./contracts";
export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}
let csrf = "";
function expired(status: number) {
  if (status === 401) window.dispatchEvent(new Event("policyiq:expired"));
}
async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  method = "GET",
  body?: unknown,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-PolicyIQ": "1",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(120000),
    });
  } catch {
    throw new ApiError(
      "The server could not be reached. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    if (!path.startsWith("/auth/")) expired(response.status);
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      typeof error.detail === "string"
        ? error.detail
        : "The request could not be completed. Please try again.",
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  const parsed = schema.safeParse(await response.json());
  if (!parsed.success)
    throw new ApiError(
      "The server returned an unexpected response. Please try again.",
    );
  return parsed.data;
}
const empty = z.void();
async function auth(path: string, body?: unknown, method = "POST") {
  const result = await request(path, sessionSchema, method, body);
  csrf = result.csrf;
  return result;
}
export const realAdapter: Adapter = {
  session: () => auth("/auth/session", undefined, "GET"),
  login: (email, password) => auth("/auth/login", { email, password }),
  signup: (name, email, password) =>
    auth("/auth/signup", { name, email, password }),
  logout: async () => {
    await request("/auth/logout", empty, "POST");
    csrf = "";
  },
  forgot: (email) =>
    request("/auth/forgot", z.object({ message: z.string() }), "POST", {
      email,
    }),
  reset: (token, password) =>
    request("/auth/reset", empty, "POST", { token, password }),
  password: (current, password) =>
    request("/auth/password", empty, "POST", { current, password }),
  profile: (name) => auth("/auth/profile", { name }, "PATCH"),
  config: () => request("/config", configSchema),
  page: (id, page) =>
    request(
      `/policies/${id}/pages/${page}`,
      z.object({ text: z.string(), page_count: z.number() }),
    ),
  policies: () => request("/policies", z.array(policySchema)),
  policy: (id) => request(`/policies/${encodeURIComponent(id)}`, policySchema),
  opened: (id) => request(`/policies/${id}/opened`, empty, "POST"),
  archive: (id, archived) =>
    request(`/policies/${id}`, empty, "PATCH", { archived }),
  deletePolicy: (id) => request(`/policies/${id}`, empty, "DELETE"),
  upload: (file, signal, progress) =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/policies");
      xhr.setRequestHeader("Content-Type", "application/pdf");
      xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
      xhr.setRequestHeader("X-PolicyIQ", "1");
      xhr.setRequestHeader("X-CSRF-Token", csrf);
      xhr.timeout = 120000;
      const abort = () => xhr.abort();
      signal.addEventListener("abort", abort, { once: true });
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable)
          progress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300)
            resolve(policySchema.parse(data));
          else {
            expired(xhr.status);
            reject(
              new ApiError(
                typeof data.detail === "string"
                  ? data.detail
                  : "Upload failed. Try again.",
                xhr.status,
              ),
            );
          }
        } catch {
          reject(
            new ApiError("The upload response was invalid. Please try again."),
          );
        }
      };
      xhr.onerror = () =>
        reject(new ApiError("Upload failed. Check your connection and retry."));
      xhr.ontimeout = () =>
        reject(
          new ApiError("Upload timed out. Check My Policies before retrying."),
        );
      xhr.onabort = () => reject(new ApiError("Upload cancelled."));
      xhr.onloadend = () => signal.removeEventListener("abort", abort);
      if (signal.aborted) abort();
      else xhr.send(file);
    }),
  conversations: (id) =>
    request(`/policies/${id}/conversations`, z.array(conversationSchema)),
  ask: (id, question, conversation_id) =>
    request(`/policies/${id}/questions`, conversationSchema, "POST", {
      question,
      conversation_id,
    }),
  claims: () => request("/claims", z.array(claimSchema)),
  saveClaim: (data, id) =>
    request(
      id ? `/claims/${id}` : "/claims",
      claimSchema,
      id ? "PUT" : "POST",
      data,
    ),
  deleteClaim: (id) => request(`/claims/${id}`, empty, "DELETE"),
  compare: (a, b) => request("/comparison", comparisonSchema, "POST", { a, b }),
};
