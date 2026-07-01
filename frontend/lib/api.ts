// ---- Types ----------------------------------------------------------------

export type AgentFrame =
  | { type: "text"; text: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "tool_result"; name: string; ok: boolean; content: string }
  | { type: "turn_complete"; stop_reason: string; usage: unknown }
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

// ---- WebSocket chat -------------------------------------------------------

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
