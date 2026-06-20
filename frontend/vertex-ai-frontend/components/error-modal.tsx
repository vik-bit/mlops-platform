"use client";

import { AlertTriangle, X } from "lucide-react";

interface ErrorModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  type?: "error" | "rate-limit";
  onDismiss: () => void;
}

export function ErrorModal({
  isOpen,
  title,
  message,
  type,
  onDismiss,
}: ErrorModalProps) {
  if (!isOpen) return null;

  const isRateLimit = type === "rate-limit";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onDismiss}
      />

      {/* Modal */}
      <div className="relative w-full max-w-md rounded-lg bg-card p-6 shadow-lg">
        {/* Close Button */}
        <button
          onClick={onDismiss}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground transition-colors"
        >
          <X size={20} />
        </button>

        {/* Content */}
        <div className="flex gap-4">
          <div
            className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full ${
              isRateLimit
                ? "bg-yellow-100 dark:bg-yellow-900/30"
                : "bg-red-100 dark:bg-red-900/30"
            }`}
          >
            <AlertTriangle
              size={24}
              className={isRateLimit ? "text-yellow-600" : "text-red-600"}
            />
          </div>

          <div className="flex-1">
            <h2 className="mb-2 text-lg font-semibold text-foreground">
              {title}
            </h2>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {message}
            </p>

            <button
              onClick={onDismiss}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity"
            >
              Got it
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}