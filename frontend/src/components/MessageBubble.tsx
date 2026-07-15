"use client";

import { useTranslations } from "next-intl";
import type { ChatMessage } from "@/types/diagnosis";
import { DiagnosisCard } from "./DiagnosisCard";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const t = useTranslations("chat");
  const isUser = message.role === "user";

  return (
    <div className={`message-row ${isUser ? "user" : "assistant"}`}>
      <span className="message-label">{isUser ? t("you") : t("assistant")}</span>
      <div className="bubble">{message.content}</div>
      {message.diagnosis ? <DiagnosisCard diagnosis={message.diagnosis} /> : null}
    </div>
  );
}
