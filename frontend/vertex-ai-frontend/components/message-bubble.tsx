interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isLoading?: boolean;
  isStreaming?: boolean;
}

export function MessageBubble({
  role,
  content,
  isLoading,
  isStreaming,
}: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
          AI
        </div>
      )}

      <div
        className={`max-w-xl rounded-lg px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card text-foreground"
        }`}
      >
        {isLoading ? (
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <div className="h-2 w-2 rounded-full bg-current opacity-70 animate-bounce" />
              <div
                className="h-2 w-2 rounded-full bg-current opacity-70 animate-bounce"
                style={{ animationDelay: "0.1s" }}
              />
              <div
                className="h-2 w-2 rounded-full bg-current opacity-70 animate-bounce"
                style={{ animationDelay: "0.2s" }}
              />
            </div>
            <span className="text-xs text-current/70">thinking…</span>
          </div>
        ) : (
          <div className="whitespace-pre-wrap break-words">
            {content ? (
              <>
                {content}
                {isStreaming && (
                  <span className="inline-block h-5 w-0.5 bg-current ml-1 animate-pulse" />
                )}
              </>
            ) : (
              <span className="text-muted-foreground italic">No response</span>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-foreground">
          U
        </div>
      )}
    </div>
  );
}