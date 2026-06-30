"use client";

import { useEffect, useRef, useState } from "react";
import { openChatSocket, type AgentFrame } from "@/lib/api";

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

  useEffect(() => {
    const ws = openChatSocket(
      convId.current,
      (frame: AgentFrame) => {
        if (frame.type === "text") {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { role: "assistant", text: last.text + frame.text }];
            }
            return [...prev, { role: "assistant", text: frame.text }];
          });
        } else if (frame.type === "turn_complete") {
          setStreaming(false);
        } else if (frame.type === "error") {
          setMessages((prev) => [...prev, { role: "assistant", text: `[error] ${frame.error}` }]);
          setStreaming(false);
        }
      },
      () => setConnected(true),
      () => setConnected(false),
    );
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  function send() {
    const text = input.trim();
    if (!text || !wsRef.current || !connected || streaming) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setStreaming(true);
    wsRef.current.send(JSON.stringify({ message: text }));
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", padding: "1rem" }}>
      <h2 style={{ margin: "0 0 1rem" }}>
        hirable chat{" "}
        <span style={{ fontSize: "0.75rem", color: connected ? "green" : "red" }}>
          {connected ? "● connected" : "○ connecting…"}
        </span>
      </h2>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          border: "1px solid #ddd",
          borderRadius: 4,
          padding: "0.75rem",
          marginBottom: "0.75rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        {messages.map((m, i) => (
          <div key={i} style={{ textAlign: m.role === "user" ? "right" : "left" }}>
            <span
              style={{
                display: "inline-block",
                background: m.role === "user" ? "#0070f3" : "#f0f0f0",
                color: m.role === "user" ? "#fff" : "#000",
                padding: "0.4rem 0.75rem",
                borderRadius: 8,
                maxWidth: "75%",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {m.text}
            </span>
          </div>
        ))}
        {streaming && (
          <div style={{ color: "#888", fontSize: "0.85rem" }}>agent is typing…</div>
        )}
      </div>

      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          style={{ flex: 1, padding: "0.5rem", borderRadius: 4, border: "1px solid #ccc" }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Type a message…"
          disabled={!connected || streaming}
        />
        <button
          style={{ padding: "0.5rem 1rem", borderRadius: 4 }}
          onClick={send}
          disabled={!connected || streaming || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}
