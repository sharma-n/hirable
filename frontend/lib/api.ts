// ---- Types ----------------------------------------------------------------

export type AgentFrame =
  | { type: "text"; text: string }
  | { type: "tool_call"; call_id: string; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; call_id: string; name: string; ok: boolean; content: string }
  | { type: "turn_complete"; stop_reason: string; usage: unknown; iterations: number }
  | { type: "error"; error: string };

export interface User {
  id: string;
  email: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at: string;
}

// ---- REST helper ----------------------------------------------------------

const backendBase =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function apiFetch<T = unknown>(
  path: string,
  opts: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${backendBase}${path}`, {
    ...opts,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers ?? {}),
    },
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      if (Array.isArray(body.detail)) {
        // Pydantic v2 validation errors: [{loc, msg, type, ...}]
        message = body.detail
          .map((e: { loc?: string[]; msg: string }) => {
            const field = e.loc?.slice(1).join(".") ?? "";
            return field ? `${field}: ${e.msg}` : e.msg;
          })
          .join("; ");
      } else if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Auth API -------------------------------------------------------------

export async function apiSignup(email: string, password: string): Promise<User> {
  return apiFetch<User>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function apiLogin(email: string, password: string): Promise<User> {
  return apiFetch<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function apiLogout(): Promise<void> {
  return apiFetch<void>("/api/auth/logout", { method: "POST" });
}

export async function apiMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

// ---- Admin API ------------------------------------------------------------

export async function apiListUsers(): Promise<User[]> {
  return apiFetch<User[]>("/api/admin/users");
}

export async function apiDeleteUser(userId: string): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}`, { method: "DELETE" });
}

export async function apiDisableUser(userId: string): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}/disable`, { method: "POST" });
}

export async function apiEnableUser(userId: string): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}/enable`, { method: "POST" });
}

export async function apiResetPassword(
  userId: string,
  newPassword: string,
): Promise<void> {
  return apiFetch<void>(`/api/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

// ---- Profile types --------------------------------------------------------

export interface SocialNetworkItem {
  network: string;
  username: string;
}

export interface ContactInfo {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  website: string;
  social_networks: SocialNetworkItem[];
  links: string[];
}

export interface ExperienceItem {
  company: string;
  position: string;    // RenderCV ExperienceEntry.position
  start_date: string;
  end_date: string;
  date: string;        // free-form; mutually exclusive with start/end
  location: string;
  summary: string;
  highlights: string[];
  tech: string[];
}

export interface ProjectItem {
  name: string;
  link: string;
  start_date: string;
  end_date: string;
  date: string;
  location: string;
  summary: string;
  highlights: string[];
  tech: string[];
}

export interface EducationItem {
  institution: string;
  area: string;        // RenderCV EducationEntry.area (field of study)
  degree: string;
  start_date: string;
  end_date: string;
  date: string;
  location: string;
  summary: string;
  highlights: string[];
}

export interface SkillItem {
  label: string;       // RenderCV OneLineEntry.label  e.g. "Programming Languages"
  details: string;     // RenderCV OneLineEntry.details e.g. "Python, Go, TypeScript"
}

export interface PublicationItem {
  title: string;
  authors: string[];
  doi: string;
  url: string;
  journal: string;
  summary: string;
  date: string;
}

export interface ExtrasItem {
  title: string;
  highlights: string[];
  tech: string[];
}

export interface EnrichmentItem {
  key: string;
  value: string;
}

export interface ProfileData {
  contact: ContactInfo;
  summary: string;
  skills: SkillItem[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  publications: PublicationItem[];
  education: EducationItem[];
  extras: ExtrasItem[];
  enrichment: EnrichmentItem[];
}

export interface Profile {
  id: string;
  user_id: string;
  version: number;
  data: ProfileData;
  updated_at: string;
}

// ---- Profile API ----------------------------------------------------------

export async function apiGetProfile(): Promise<Profile | null> {
  const res = await fetch(`${backendBase}/api/profile`, {
    credentials: "include",
  });
  if (res.status === 204) return null;
  if (!res.ok) throw new Error(res.statusText);
  return res.json() as Promise<Profile>;
}

export async function apiUpdateProfile(data: ProfileData): Promise<Profile> {
  return apiFetch<Profile>("/api/profile", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export interface ProfileVersion {
  id: string;
  version: number;
  source: "user" | "agent" | "restore";
  created_at: string;
}

export async function apiListProfileVersions(): Promise<ProfileVersion[]> {
  return apiFetch<ProfileVersion[]>("/api/profile/versions");
}

export async function apiRestoreProfileVersion(versionId: string): Promise<Profile> {
  return apiFetch<Profile>(`/api/profile/versions/${versionId}/restore`, { method: "POST" });
}

export async function apiUploadResume(file: File): Promise<Profile> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${backendBase}/api/profile/resume`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return res.json() as Promise<Profile>;
}

// ---- Jobs types -------------------------------------------------------------

export interface JobData {
  company: string;
  title: string;
  location: string;
  responsibilities: string[];
  must_have: string[];
  nice_to_have: string[];
  keywords: string[];
  why_opened_guess: string;
  seniority: string;
  company_type: string;
  team_name: string;
  team_description: string;
}

export interface Job {
  id: string;
  user_id: string;
  source_url: string | null;
  raw_text: string;
  parsed: JobData;
  created_at: string;
  updated_at: string;
}

export interface JobCreateResult {
  needs_paste: boolean;
  job: Job | null;
}

// ---- Jobs API ---------------------------------------------------------------

export async function apiListJobs(): Promise<Job[]> {
  return apiFetch<Job[]>("/api/jobs");
}

export async function apiAddJob(body: {
  url?: string;
  raw_text?: string;
}): Promise<JobCreateResult> {
  return apiFetch<JobCreateResult>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function apiGetJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/api/jobs/${jobId}`);
}

export async function apiUpdateJob(jobId: string, data: JobData): Promise<Job> {
  return apiFetch<Job>(`/api/jobs/${jobId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function apiDeleteJob(jobId: string): Promise<void> {
  return apiFetch<void>(`/api/jobs/${jobId}`, { method: "DELETE" });
}

// ---- Documents (M5 — CV generation) types ----------------------------------

export interface DocumentListItem {
  id: string;
  job_id: string;
  type: string;
  version: number;
  is_finalized: boolean;
  created_at: string;
}

export interface DocumentDetail extends DocumentListItem {
  source_format: string;
  source_text: string;
}

export interface CompileErrorDetail {
  stage: "yaml" | "schema" | "render";
  errors: string[];
}

export class CompileFailure extends Error {
  detail: CompileErrorDetail;
  constructor(detail: CompileErrorDetail) {
    super(detail.errors.join("; "));
    this.detail = detail;
  }
}

// ---- Documents API ----------------------------------------------------------

export async function apiDraftCv(jobId: string, instructions?: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>("/api/documents/draft", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, instructions: instructions || undefined }),
  });
}

export async function apiDraftCoverLetter(jobId: string, instructions?: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>("/api/documents/draft-cover-letter", {
    method: "POST",
    body: JSON.stringify({ job_id: jobId, instructions: instructions || undefined }),
  });
}

export async function apiListDocuments(
  jobId: string,
  type: "cv" | "cover_letter" = "cv",
): Promise<DocumentListItem[]> {
  return apiFetch<DocumentListItem[]>(`/api/documents?job_id=${jobId}&type=${type}`);
}

export async function apiGetDocument(documentId: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/api/documents/${documentId}`);
}

export async function apiSaveDocument(documentId: string, sourceText: string): Promise<DocumentDetail> {
  return apiFetch<DocumentDetail>(`/api/documents/${documentId}`, {
    method: "PUT",
    body: JSON.stringify({ source_text: sourceText }),
  });
}

export async function apiDeleteDocument(documentId: string): Promise<void> {
  return apiFetch<void>(`/api/documents/${documentId}`, { method: "DELETE" });
}

export async function apiCompileDocument(sourceText: string): Promise<Blob> {
  const res = await fetch(`${backendBase}/api/documents/compile`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_text: sourceText }),
  });
  if (!res.ok) {
    let detail: CompileErrorDetail = { stage: "render", errors: [res.statusText] };
    try {
      const body = (await res.json()) as { detail?: CompileErrorDetail };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new CompileFailure(detail);
  }
  return res.blob();
}

// ---- Chat / agent API -------------------------------------------------------

export interface SelectableModel {
  display_name: string;
  model_id: string;
}

export async function apiListModels(): Promise<SelectableModel[]> {
  const res = await apiFetch<{ models: SelectableModel[] }>("/api/chat/models");
  return res.models;
}

export function openChatSocket(
  conversationId: string,
  onFrame: (frame: AgentFrame) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WebSocket {
  const backendWsBase = backendBase.replace(/^http/, "ws");
  const ws = new WebSocket(`${backendWsBase}/api/chat/ws/${conversationId}`);

  ws.onopen = () => onOpen?.();
  ws.onclose = () => onClose?.();
  ws.onmessage = (ev) => {
    try {
      onFrame(JSON.parse(ev.data) as AgentFrame);
    } catch {
      // ignore malformed frames
    }
  };

  return ws;
}
