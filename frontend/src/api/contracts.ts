import { z } from "zod";
export const userSchema = z.object({
  id: z.string(),
  name: z.string(),
  email: z.string(),
});
export const sessionSchema = z.object({ user: userSchema, csrf: z.string() });
export const policySchema = z.object({
  id: z.string(),
  filename: z.string(),
  page_count: z.number(),
  created_at: z.string(),
  last_opened: z.string().nullable(),
  archived: z.boolean(),
  warnings: z.array(z.string()),
  original_available: z.boolean(),
});
export const sourceSchema = z.object({
  policy_id: z.string(),
  passage_id: z.string(),
  page_start: z.number(),
  page_end: z.number(),
  section: z.string().nullable().optional(),
  text: z.string(),
  quote: z.string().optional(),
});
export const answerSchema = z.object({
  status: z.enum(["verified", "insufficient_evidence"]),
  text: z.string(),
  claims: z.array(
    z.object({ text: z.string(), sources: z.array(sourceSchema) }),
  ),
  missing_information: z.array(z.string()),
  sources: z.array(sourceSchema),
  warnings: z.array(z.string()),
});
export const messageSchema = z.object({
  id: z.string(),
  question: z.string(),
  answer: answerSchema,
  created_at: z.string(),
});
export const conversationSchema = z.object({
  id: z.string(),
  policy_id: z.string(),
  title: z.string(),
  messages: z.array(messageSchema),
});
export const claimSchema = z.object({
  id: z.string(),
  policy_id: z.string(),
  description: z.string(),
  incident_date: z.string(),
  gathered: z.array(z.string()),
  updated_at: z.string(),
});
const findingSchema = z.object({
  status: z.enum(["supported", "uncertain", "not_found"]),
  summary: z.string(),
  amounts: z.array(z.string()),
  evidence: z.array(sourceSchema),
});
export const comparisonSchema = z.object({
  categories: z.array(
    z.object({
      category: z.string(),
      label: z.string(),
      finding_a: findingSchema,
      finding_b: findingSchema,
    }),
  ),
  limitations: z.array(z.string()),
});
export const configSchema = z.object({
  questions_enabled: z.boolean(),
  processing: z.string(),
  reset_delivery: z.string(),
});
export type User = z.infer<typeof userSchema>;
export type Session = z.infer<typeof sessionSchema>;
export type Policy = z.infer<typeof policySchema>;
export type Source = z.infer<typeof sourceSchema>;
export type Answer = z.infer<typeof answerSchema>;
export type Conversation = z.infer<typeof conversationSchema>;
export type Claim = z.infer<typeof claimSchema>;
export type Comparison = z.infer<typeof comparisonSchema>;
export type Config = z.infer<typeof configSchema>;
export type ClaimInput = Omit<Claim, "id" | "updated_at">;
export interface Adapter {
  session(): Promise<Session>;
  login(email: string, password: string): Promise<Session>;
  signup(name: string, email: string, password: string): Promise<Session>;
  logout(): Promise<void>;
  forgot(email: string): Promise<{ message: string }>;
  reset(token: string, password: string): Promise<void>;
  password(current: string, password: string): Promise<void>;
  profile(name: string): Promise<Session>;
  config(): Promise<Config>;
  page(id: string, page: number): Promise<{ text: string; page_count: number }>;
  policies(): Promise<Policy[]>;
  upload(
    file: File,
    signal: AbortSignal,
    progress: (value: number) => void,
  ): Promise<Policy>;
  policy(id: string): Promise<Policy>;
  opened(id: string): Promise<void>;
  archive(id: string, archived: boolean): Promise<void>;
  deletePolicy(id: string): Promise<void>;
  conversations(id: string): Promise<Conversation[]>;
  ask(
    id: string,
    question: string,
    conversation_id?: string,
  ): Promise<Conversation>;
  claims(): Promise<Claim[]>;
  saveClaim(data: ClaimInput, id?: string): Promise<Claim>;
  deleteClaim(id: string): Promise<void>;
  compare(a: string, b: string): Promise<Comparison>;
}
