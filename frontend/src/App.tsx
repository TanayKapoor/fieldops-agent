import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_BASE = "http://localhost:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
  toolCalls?: string[]; // muted summary lines, e.g. ["→ update_status(WO-002, In Progress)"]
};

type WorkOrder = {
  id: string;
  status: string;
};

function buildGreeting(workOrders: WorkOrder[]): string {
  if (workOrders.length === 0) {
    return "You have no work orders assigned right now.";
  }
  const open = workOrders.filter((wo) => wo.status !== "Completed");
  if (open.length === 0) {
    return `You have ${workOrders.length} work orders, all completed.`;
  }
  const ids = open.map((wo) => wo.id).join(", ");
  return `You have ${open.length} open work order${open.length === 1 ? "" : "s"}: ${ids}`;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/work-orders`)
      .then((res) => res.json())
      .then((workOrders: WorkOrder[]) => {
        setMessages((prev) =>
          prev.length === 0 ? [{ role: "assistant", content: buildGreeting(workOrders) }] : prev
        );
      })
      .catch(() => {
        setMessages((prev) =>
          prev.length === 0 ? [{ role: "assistant", content: "Couldn't load your work orders." }] : prev
        );
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });
      if (!res.ok) {
        throw new Error(`chat request failed: ${res.status}`);
      }
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, toolCalls: data.tool_calls },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong reaching the server." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      sendMessage();
    }
  }

  return (
    <>
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message-row ${msg.role}`}>
            {msg.toolCalls?.map((line, j) => (
              <div
                key={j}
                className={`tool-call-line ${line.startsWith("✗") ? "rejected" : ""}`}
              >
                {line}
              </div>
            ))}
            <div className="bubble">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <div className="input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a work order..."
          disabled={loading}
        />
        <button onClick={sendMessage} disabled={loading}>
          {loading ? "..." : "Send"}
        </button>
      </div>
    </>
  );
}

export default App;
