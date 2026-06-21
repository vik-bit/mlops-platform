"use client";

import { useState, useRef, useEffect } from "react";
import { ChatInput } from "@/components/chat-input";
import { MessageBubble } from "@/components/message-bubble";
import { ErrorModal } from "@/components/error-modal";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const API_URL = "https://mlops-ai-service.onrender.com/copilot/chat";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "MLOps Copilot ready. How can I help?" },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<{
    type: "error" | "rate-limit";
    message: string;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || isSending) return;

    const userMsg: Message = { role: "user", content: trimmed };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setIsSending(true);

    abortControllerRef.current = new AbortController();

    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("mlops_token")
          : null;

      const res = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: trimmed }),
        signal: abortControllerRef.current.signal,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          data.detail ||
          (res.status === 429
            ? "AI service is at capacity. Please try again shortly."
            : "Something went wrong. Please try again.");

        setError({
          type: res.status === 429 ? "rate-limit" : "error",
          message: detail,
        });
        setIsSending(false);
        return;
      }

      // Backend returns one complete JSON object — { response, context_length, tools_used }
      // NOT a server-sent event stream. The previous version tried to read
      // res.body as an SSE stream and looked for a "content" field that
      // never existed in this payload shape, so hasContent stayed false
      // and nothing ever rendered even though the network tab showed 200.
      const data = await res.json();

      if (!data.response) {
        setError({
          type: "error",
          message: "No response field in the AI service reply.",
        });
        setIsSending(false);
        return;
      }

      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.response },
      ]);
      setIsSending(false);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setIsSending(false);
        return;
      }
      setError({
        type: "error",
        message:
          "Could not reach the AI service. Is it running? Please check your connection and try again.",
      });
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="border-b border-border bg-card px-4 py-4 sm:px-6">
        <div className="mx-auto max-w-2xl">
          <h1 className="text-xl font-semibold text-foreground">
            MLOps Copilot
          </h1>
          <p className="text-sm text-muted-foreground">
            AI-powered assistance for your ML operations
          </p>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-6 px-4 py-6 sm:px-6">
          {messages.map((message, index) => (
            <MessageBubble
              key={index}
              role={message.role}
              content={message.content}
            />
          ))}
          {/* isLoading (not isStreaming) is the prop MessageBubble actually
              checks to render the bouncing three-dot indicator. This was
              previously passed as isStreaming, which MessageBubble doesn't
              read at all — so isLoading stayed undefined/falsy, the dots
              never rendered, and the empty-content fallback ("No response")
              showed instead for the entire wait. */}
          {isSending && (
            <MessageBubble role="assistant" content="" isLoading />
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      <footer className="border-t border-border bg-background px-4 py-4 sm:px-6">
        <div className="mx-auto max-w-2xl">
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={sendMessage}
            isDisabled={isSending}
            placeholder="Ask me anything about your MLOps..."
          />
        </div>
      </footer>

      <ErrorModal
        isOpen={error !== null}
        title={error?.type === "rate-limit" ? "Rate Limit Reached" : "Error"}
        message={error?.message || ""}
        type={error?.type}
        onDismiss={() => setError(null)}
      />
    </div>
  );
}