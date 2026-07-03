"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, RotateCcw, Send, Wrench } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  apiListModels,
  openChatSocket,
  type AgentFrame,
  type SelectableModel,
} from "@/lib/api";

// Compact overrides so markdown block elements (which carry browser default
// margins) fit a chat bubble instead of a full document layout.
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-4 mb-2 last:mb-0 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 last:mb-0 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10 text-[0.85em] font-mono">
      {children}
    </code>
  ),
  h1: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
  h2: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
  h3: ({ children }) => <p className="font-semibold mb-1">{children}</p>,
};

// ── Message / part model ─────────────────────────────────────────────────────

type MessagePart =
  | { kind: "text"; text: string }
  | { kind: "tool_call"; call_id: string; name: string; arguments: Record<string, unknown> }
  | { kind: "tool_result"; call_id: string; name: string; ok: boolean; content: string };

interface Message {
  role: "user" | "assistant";
  parts: MessagePart[];
}

function lastAssistantMessageInProgress(messages: Message[]): boolean {
  const last = messages[messages.length - 1];
  return last?.role === "assistant";
}

// ── Tool activity chip ───────────────────────────────────────────────────────

function ToolCallChip({ part }: { part: Extract<MessagePart, { kind: "tool_call" }> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="max-w-[85%] rounded-lg border bg-muted/40 text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 w-full text-left text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <Wrench className="size-3" />
        <span className="font-mono">{part.name}</span>
      </button>
      {open && (
        <pre className="px-2.5 pb-2 text-[11px] whitespace-pre-wrap break-words text-muted-foreground">
          {JSON.stringify(part.arguments, null, 2)}
        </pre>
      )}
    </div>
  );
}

function ToolResultChip({ part }: { part: Extract<MessagePart, { kind: "tool_result" }> }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={cn(
        "max-w-[85%] rounded-lg border text-xs",
        part.ok ? "bg-muted/40" : "border-destructive/40 bg-destructive/5",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 w-full text-left text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <span>{part.ok ? "✓" : "✗"}</span>
        <span className="font-mono">{part.name}</span>
      </button>
      {open && (
        <pre className="px-2.5 pb-2 text-[11px] whitespace-pre-wrap break-words text-muted-foreground">
          {part.content}
        </pre>
      )}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────

export interface AgentPanelProps {
  /** "profile" | `job:${jobId}` — the client-chosen conversation-id base. */
  conversationBase: string;
  emptyStateTitle: string;
  emptyStateSubtitle: string;
  /** One-click starter message shown above the composer, only while the conversation is empty. */
  starterPrompt?: string;
  onToolResult?: (name: string, ok: boolean, content: string) => void;
}

function generationKey(base: string): string {
  return `hirable-conv-gen:${base}`;
}

function readGeneration(base: string): number {
  if (typeof window === "undefined") return 0;
  const raw = window.localStorage.getItem(generationKey(base));
  const n = raw ? parseInt(raw, 10) : 0;
  return Number.isFinite(n) ? n : 0;
}

// The underlying agent_kit conversation persists server-side (same conversationId
// = same session, resumed on reconnect) regardless of whether this component is
// mounted — so without this, navigating away and back would silently desync the
// displayed transcript from what the agent actually remembers. Mirror it
// client-side, keyed by conversationId, so reopening the page shows the same
// conversation the agent is still continuing.
function messagesKey(conversationId: string): string {
  return `hirable-conv-messages:${conversationId}`;
}

function loadStoredMessages(conversationId: string): Message[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(messagesKey(conversationId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Message[]) : [];
  } catch {
    return [];
  }
}

function storeMessages(conversationId: string, messages: Message[]): void {
  try {
    window.localStorage.setItem(messagesKey(conversationId), JSON.stringify(messages));
  } catch {
    // localStorage unavailable/full — non-fatal, just lose persistence for this update.
  }
}

export function AgentPanel({
  conversationBase,
  emptyStateTitle,
  emptyStateSubtitle,
  starterPrompt,
  onToolResult,
}: AgentPanelProps) {
  const [generation, setGeneration] = useState(() => readGeneration(conversationBase));
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [models, setModels] = useState<SelectableModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const conversationId = generation === 0 ? conversationBase : `${conversationBase}.${generation}`;

  // The WS effect below only re-runs when conversationId changes, so its onFrame
  // closure would otherwise capture whichever onToolResult was passed in at that
  // point (typically mount) forever, silently going stale on every later parent
  // re-render. Route through a ref, kept current every render, so the frame
  // handler always calls the latest version.
  const onToolResultRef = useRef(onToolResult);
  useEffect(() => {
    onToolResultRef.current = onToolResult;
  }, [onToolResult]);

  useEffect(() => {
    apiListModels()
      .then(setModels)
      .catch(() => {
        // Non-fatal — the picker just stays empty.
      });
  }, []);

  useEffect(() => {
    setMessages(loadStoredMessages(conversationId));
    setStreaming(false);

    // Wraps setMessages so every update is mirrored to localStorage under this
    // effect's own conversationId — safe to close over directly here (unlike
    // onToolResult above) since conversationId is this effect's own dependency,
    // so it can never be stale for the lifetime of this WS connection.
    function updateMessages(updater: (prev: Message[]) => Message[]) {
      setMessages((prev) => {
        const next = updater(prev);
        storeMessages(conversationId, next);
        return next;
      });
    }

    const ws = openChatSocket(
      conversationId,
      (frame: AgentFrame) => {
        if (frame.type === "text") {
          updateMessages((prev) => {
            if (lastAssistantMessageInProgress(prev)) {
              const last = prev[prev.length - 1];
              const parts = [...last.parts];
              const lastPart = parts[parts.length - 1];
              if (lastPart?.kind === "text") {
                parts[parts.length - 1] = { kind: "text", text: lastPart.text + frame.text };
              } else {
                parts.push({ kind: "text", text: frame.text });
              }
              return [...prev.slice(0, -1), { role: "assistant", parts }];
            }
            return [...prev, { role: "assistant", parts: [{ kind: "text", text: frame.text }] }];
          });
        } else if (frame.type === "tool_call") {
          updateMessages((prev) => {
            const part: MessagePart = {
              kind: "tool_call",
              call_id: frame.call_id,
              name: frame.name,
              arguments: frame.arguments,
            };
            if (lastAssistantMessageInProgress(prev)) {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), { role: "assistant", parts: [...last.parts, part] }];
            }
            return [...prev, { role: "assistant", parts: [part] }];
          });
        } else if (frame.type === "tool_result") {
          updateMessages((prev) => {
            const part: MessagePart = {
              kind: "tool_result",
              call_id: frame.call_id,
              name: frame.name,
              ok: frame.ok,
              content: frame.content,
            };
            if (lastAssistantMessageInProgress(prev)) {
              const last = prev[prev.length - 1];
              return [...prev.slice(0, -1), { role: "assistant", parts: [...last.parts, part] }];
            }
            return [...prev, { role: "assistant", parts: [part] }];
          });
          onToolResultRef.current?.(frame.name, frame.ok, frame.content);
        } else if (frame.type === "turn_complete") {
          setStreaming(false);
        } else if (frame.type === "error") {
          updateMessages((prev) => [
            ...prev,
            { role: "assistant", parts: [{ kind: "text", text: `Error: ${frame.error}` }] },
          ]);
          setStreaming(false);
        }
      },
      () => setConnected(true),
      () => setConnected(false),
    );
    wsRef.current = ws;
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || !wsRef.current || !connected || streaming) return;
    setMessages((prev) => {
      const next: Message[] = [...prev, { role: "user", parts: [{ kind: "text", text }] }];
      storeMessages(conversationId, next);
      return next;
    });
    setInput("");
    setStreaming(true);
    wsRef.current.send(JSON.stringify({ message: text }));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function handleModelChange(modelId: string) {
    setSelectedModel(modelId);
    wsRef.current?.send(JSON.stringify({ type: "set_model", model: modelId || null }));
  }

  function handleNewChat() {
    const next = generation + 1;
    window.localStorage.setItem(generationKey(conversationBase), String(next));
    setGeneration(next);
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-2 px-3 py-2 border-b bg-muted/30 text-xs text-muted-foreground">
        <span
          className={cn(
            "size-1.5 rounded-full",
            connected ? "bg-green-500" : "bg-muted-foreground/40 animate-pulse",
          )}
        />
        {connected ? "Connected" : "Connecting…"}
        <div className="flex-1" />
        {models.length > 0 && (
          <select
            value={selectedModel}
            onChange={(e) => handleModelChange(e.target.value)}
            className="rounded-md border bg-background px-1.5 py-0.5 text-xs"
            aria-label="Model"
          >
            <option value="">Default</option>
            {models.map((m) => (
              <option key={m.model_id} value={m.model_id}>
                {m.display_name}
              </option>
            ))}
          </select>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="New chat"
          onClick={handleNewChat}
          title="Start a new conversation"
        >
          <RotateCcw className="size-3.5" />
        </Button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-3 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-1.5 select-none px-4">
            <p className="text-sm font-medium">{emptyStateTitle}</p>
            <p className="text-xs">{emptyStateSubtitle}</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex flex-col gap-1.5", m.role === "user" ? "items-end" : "items-start")}>
            {m.parts.map((part, j) => {
              if (part.kind === "text") {
                return (
                  <div
                    key={j}
                    className={cn(
                      "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm break-words leading-relaxed",
                      m.role === "user"
                        ? "bg-primary text-primary-foreground rounded-br-sm"
                        : "bg-muted text-foreground rounded-bl-sm",
                    )}
                  >
                    <ReactMarkdown components={markdownComponents}>{part.text}</ReactMarkdown>
                  </div>
                );
              }
              if (part.kind === "tool_call") return <ToolCallChip key={j} part={part} />;
              return <ToolResultChip key={j} part={part} />;
            })}
          </div>
        ))}
        {streaming && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-2xl rounded-bl-sm px-3.5 py-2">
              <span className="flex gap-1">
                <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                <span className="size-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="shrink-0 border-t bg-background px-3 py-2.5">
        {starterPrompt && messages.length === 0 && (
          <button
            type="button"
            onClick={() => send(starterPrompt)}
            disabled={!connected || streaming}
            className={cn(
              "mb-2 w-full text-left rounded-xl border border-dashed px-3 py-2 text-xs",
              "text-muted-foreground hover:text-foreground hover:border-solid hover:bg-muted/50",
              "disabled:opacity-50 disabled:cursor-not-allowed transition-colors",
            )}
          >
            ✨ {starterPrompt}
          </button>
        )}
        <div className="flex items-end gap-2">
          <textarea
            rows={1}
            className={cn(
              "flex-1 resize-none rounded-xl border bg-muted/50 px-3 py-2 text-sm leading-relaxed",
              "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring",
              "placeholder:text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed",
              "max-h-32 overflow-y-auto",
            )}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 128)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder="Message the assistant…"
            disabled={!connected || streaming}
          />
          <Button
            size="icon"
            onClick={() => send()}
            disabled={!connected || streaming || !input.trim()}
            className="shrink-0 rounded-xl"
            aria-label="Send message"
          >
            {streaming ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
