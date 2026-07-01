"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { openChatSocket, type AgentFrame } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface Message {
  role: "user" | "assistant";
  text: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const convId = useRef(`conv-${Math.random().toString(36).slice(2)}`);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const ws = openChatSocket(
      convId.current,
      (frame: AgentFrame) => {
        if (frame.type === "text") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { role: "assistant", text: last.text + frame.text },
              ];
            }
            return [...prev, { role: "assistant", text: frame.text }];
          });
        } else if (frame.type === "turn_complete") {
          setStreaming(false);
        } else if (frame.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", text: `Error: ${frame.error}` },
          ]);
          setStreaming(false);
        }
      },
      () => setConnected(true),
      () => setConnected(false),
    );
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send() {
    const text = input.trim();
    if (!text || !wsRef.current || !connected || streaming) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
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

  return (
    <div className="flex flex-col flex-1 h-[calc(100vh-3.5rem)]">
      {/* Connection status bar */}
      <div className="shrink-0 flex items-center gap-2 px-4 py-2 border-b bg-muted/30 text-xs text-muted-foreground">
        <span
          className={cn(
            "size-1.5 rounded-full",
            connected ? "bg-green-500" : "bg-muted-foreground/40 animate-pulse",
          )}
        />
        {connected ? "Connected" : "Connecting…"}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground gap-2 select-none">
            <p className="text-lg font-medium">How can I help you today?</p>
            <p className="text-sm">Ask me to review your resume, tailor your CV, or help with a cover letter.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
          >
            <div
              className={cn(
                "max-w-[75%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap break-words leading-relaxed",
                m.role === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-muted text-foreground rounded-bl-sm",
              )}
            >
              {m.text}
            </div>
          </div>
        ))}
        {streaming && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-2.5">
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
      <div className="shrink-0 border-t bg-background px-4 py-3">
        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          <textarea
            rows={1}
            className={cn(
              "flex-1 resize-none rounded-xl border bg-muted/50 px-3 py-2.5 text-sm leading-relaxed",
              "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring",
              "placeholder:text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed",
              "max-h-40 overflow-y-auto",
            )}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              // Auto-resize
              e.target.style.height = "auto";
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
            onKeyDown={handleKeyDown}
            placeholder="Message hirable…"
            disabled={!connected || streaming}
          />
          <Button
            size="icon"
            onClick={send}
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
