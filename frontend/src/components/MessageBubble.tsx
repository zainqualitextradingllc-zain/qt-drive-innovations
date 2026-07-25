"use client";

import { useTranslations } from "next-intl";
import type { ChatMessage, Locale } from "@/types/diagnosis";
import { DiagnosisCard } from "./DiagnosisCard";

export function MessageBubble({
  message,
  sessionId,
  locale,
  diagnosisCategory,
  showLead = false,
}: {
  message: ChatMessage;
  sessionId: string;
  locale: Locale;
  diagnosisCategory: string;
  showLead?: boolean;
}) {
  const t = useTranslations("chat");
  const isUser = message.role === "user";

  return (
    <div className={`message-row ${isUser ? "user" : "assistant"}`}>
      <span className="message-label">{isUser ? t("you") : t("assistant")}</span>
      <div className="bubble">{message.content}</div>
      {message.diagnosis ? (
        <DiagnosisCard
          diagnosis={message.diagnosis}
          sessionId={sessionId}
          locale={locale}
          diagnosisCategory={diagnosisCategory}
          showLead={showLead}
        />
      ) : null}
    </div>
  );
}
