"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { sendChatMessage } from "@/lib/api";
import type { ChatMessage, Locale, VehicleContext } from "@/types/diagnosis";
import { MessageBubble } from "./MessageBubble";
import { VehicleChip } from "./VehicleChip";

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ChatInterface() {
  const t = useTranslations();
  const locale = useLocale() as Locale;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [vehicle, setVehicle] = useState<VehicleContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const resetSession = useCallback(() => {
    setMessages([]);
    setSessionId(null);
    setVehicle(null);
    setError(null);
    setInput("");
  }, []);

  // Reset conversation memory when language tab changes (UI chrome switches;
  // new session language is sent to the LLM on the next message)
  const prevLocale = useRef(locale);
  useEffect(() => {
    if (prevLocale.current !== locale) {
      prevLocale.current = locale;
      // Keep messages visible but clear session so backend uses new language cleanly
      setSessionId(null);
    }
  }, [locale]);

  async function onSubmit(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setError(null);
    setInput("");
    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChatMessage({
        message: text,
        language: locale,
        sessionId,
        vehicle,
      });
      setSessionId(res.session_id);
      if (res.vehicle) setVehicle(res.vehicle);

      const assistantMsg: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: res.reply,
        diagnosis: res.diagnosis || null,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setError(t("errors.network"));
    } finally {
      setLoading(false);
      taRef.current?.focus();
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void onSubmit();
    }
  }

  return (
    <div className="chat-main">
      <VehicleChip vehicle={vehicle} />
      {error ? <div className="error-banner">{error}</div> : null}

      <div className="messages" role="log" aria-live="polite">
        {messages.length === 0 ? (
          <div className="welcome-card">
            <h1>{t("chat.welcomeTitle")}</h1>
            <p>{t("chat.welcomeBody")}</p>
          </div>
        ) : null}

        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}

        {loading ? <div className="typing">{t("chat.sending")}</div> : null}
        <div ref={bottomRef} />
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <div className="composer-tools">
          <button type="button" className="btn-ghost" onClick={resetSession}>
            {t("chat.newSession")}
          </button>
        </div>
        <div className="composer-row">
          <textarea
            ref={taRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t("chat.placeholder")}
            rows={1}
            disabled={loading}
            aria-label={t("chat.placeholder")}
          />
          <button
            className="btn btn-primary"
            type="submit"
            disabled={loading || !input.trim()}
            aria-label={t("chat.send")}
          >
            {loading ? "…" : t("chat.send")}
          </button>
        </div>
      </form>
    </div>
  );
}
