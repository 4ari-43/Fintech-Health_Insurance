import type {
  Adapter,
  Policy,
  Session,
  Conversation,
  Claim,
} from "./contracts";
import { ApiError } from "./real";
const now = () => new Date().toISOString();
let session: Session | null = {
  user: { id: "demo-user", name: "Alex Morgan", email: "alex@example.test" },
  csrf: "demo-only",
};
let policies: Policy[] = [];
let conversations: Conversation[] = [];
let claims: Claim[] = [];
export function loadSamples() {
  if (!policies.length)
    policies = ["Cedar Health — Essential", "Harbor Health — Plus"].map(
      (name, i) => ({
        id: `sample-${i + 1}`,
        filename: `${name}.pdf`,
        page_count: 1,
        created_at: now(),
        last_opened: null,
        archived: false,
        warnings: ["Fictional sample policy. For interface exploration only."],
        original_available: false,
      }),
    );
}
export const sampleText =
  "The individual in-network annual deductible is $750. Prior authorization is required for planned inpatient admissions. Emergency services do not require prior authorization. Cosmetic procedures are excluded unless medically necessary following an accident.";
function needSession() {
  if (!session)
    throw new ApiError("Your session has ended. Please log in.", 401);
  return session;
}
export const demoAdapter: Adapter = {
  session: async () => needSession(),
  login: async (email) =>
    (session = {
      user: { id: "demo-user", name: "Alex Morgan", email },
      csrf: "demo-only",
    }),
  signup: async (name, email) =>
    (session = { user: { id: "demo-user", name, email }, csrf: "demo-only" }),
  logout: async () => {
    session = null;
    policies = [];
    conversations = [];
    claims = [];
  },
  forgot: async () => ({
    message:
      "Demo only: no email was sent. Real reset delivery must be configured on the server.",
  }),
  reset: async () => {
    throw new ApiError("Password reset is unavailable in this demonstration.");
  },
  password: async () => {
    throw new ApiError("Demo accounts have no stored password.");
  },
  profile: async (name) => {
    const s = needSession();
    s.user.name = name;
    return s;
  },
  config: async () => ({
    questions_enabled: true,
    processing:
      "Fictional fixtures in browser memory. Nothing is sent to a model.",
    reset_delivery: "Unavailable in demo",
  }),
  page: async () => ({ text: sampleText, page_count: 1 }),
  policies: async () => {
    needSession();
    return [...policies];
  },
  policy: async (id) => {
    const p = policies.find((p) => p.id === id);
    if (!p) throw new ApiError("Policy not found.", 404);
    return { ...p };
  },
  upload: async () => {
    throw new ApiError(
      "Demo mode does not upload documents. Explore a sample policy, or start the app in real mode.",
    );
  },
  opened: async (id) => {
    const p = policies.find((p) => p.id === id);
    if (p) p.last_opened = now();
  },
  archive: async (id, archived) => {
    const p = policies.find((p) => p.id === id);
    if (p) p.archived = archived;
  },
  deletePolicy: async (id) => {
    policies = policies.filter((p) => p.id !== id);
    conversations = conversations.filter((c) => c.policy_id !== id);
    claims = claims.filter((c) => c.policy_id !== id);
  },
  conversations: async (id) => conversations.filter((c) => c.policy_id === id),
  ask: async (id, question, conversation_id) => {
    const source = {
      policy_id: id,
      passage_id: `${id}-p1`,
      page_start: 1,
      page_end: 1,
      section: "Sample terms",
      text: sampleText,
      quote:
        "Prior authorization is required for planned inpatient admissions.",
    };
    let c = conversations.find(
      (c) => c.id === conversation_id && c.policy_id === id,
    );
    if (!c) {
      c = {
        id: crypto.randomUUID(),
        policy_id: id,
        title: question,
        messages: [],
      };
      conversations.push(c);
    }
    c.messages.push({
      id: crypto.randomUUID(),
      question,
      created_at: now(),
      answer: {
        status: "insufficient_evidence",
        text: "This demonstration shows how an answer and its sources appear. It is not an answer to your question.",
        claims: [],
        missing_information: [],
        sources: [source],
        warnings: [
          "Illustrative source; no model generation or verification was performed.",
        ],
      },
    });
    return structuredClone(c);
  },
  claims: async () => [...claims],
  saveClaim: async (data, id) => {
    const c = { ...data, id: id ?? crypto.randomUUID(), updated_at: now() };
    claims = claims.filter((x) => x.id !== c.id);
    claims.push(c);
    return c;
  },
  deleteClaim: async (id) => {
    claims = claims.filter((c) => c.id !== id);
  },
  compare: async (a, b) => ({
    categories: [
      "Deductibles",
      "Copayments and coinsurance",
      "Out-of-pocket maximum",
      "Exclusions",
      "Prior authorization",
      "Emergency care",
      "Out-of-network care",
      "Limits",
      "Waiting periods",
    ].map((label, i) => ({
      category: String(i),
      label,
      finding_a: {
        status: "supported",
        summary: "Illustrative evidence only.",
        amounts: [],
        evidence: [
          {
            policy_id: a,
            passage_id: a + "-p1",
            page_start: 1,
            page_end: 1,
            text: sampleText,
          },
        ],
      },
      finding_b: {
        status: "not_found",
        summary: "Not established in fictional policy " + b,
        amounts: [],
        evidence: [],
      },
    })),
    limitations: [
      "Demo comparison. No benefit equivalence or financial difference has been established.",
    ],
  }),
};
