export type AgentFrame =
  | { type: "text"; text: string }
  | { type: "tool_call"; name: string; arguments: string }
  | { type: "tool_result"; name: string; ok: boolean; content: string }
  | { type: "turn_complete"; stop_reason: string; usage: unknown }
  | { type: "error"; error: string };

export function openChatSocket(
  conversationId: string,
  onFrame: (frame: AgentFrame) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WebSocket {
  // In the browser, connect to the backend proxy via the public URL.
  const backendWsBase =
    process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/^http/, "ws") ?? "ws://localhost:8000";
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
