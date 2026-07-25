"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { sendChatMessage } from "@/lib/api";
import { guessCategory } from "@/lib/guessCategory";
import { captureEvent, identifyAnonymous } from "@/lib/posthog";
import { getSessionId, resetSessionId } from "@/lib/session";
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
  const [sessionId, setSessionId] = useState<string>("");
  const [vehicle, setVehicle] = useState<VehicleContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diagnosisCategory, setDiagnosisCategory] = useState("other");
  const bottomRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(false);
  const awaitingClarifyAnswerRef = useRef(false);
  const lastQuestionNumberRef = useRef(0);
  const userTurnCountRef = useRef(0);
  const categoryRef = useRef("other");

  // Init analytics session + session_started once per mount
  useEffect(() => {
    const id = getSessionId();
    setSessionId(id);
    if (!startedRef.current) {
      startedRef.current = true;
      identifyAnonymous(id);
      captureEvent("session_started", {
        session_id: id,
        locale,
        is_embedded: window.self !== window.top,
        referrer: typeof document !== "undefined" ? document.referrer || "" : "",
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fire once on mount
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const resetSession = useCallback(() => {
    const id = resetSessionId();
    setMessages([]);
    setSessionId(id);
    setVehicle(null);
    setError(null);
    setInput("");
    setDiagnosisCategory("other");
    categoryRef.current = "other";
    awaitingClarifyAnswerRef.current = false;
    lastQuestionNumberRef.current = 0;
    userTurnCountRef.current = 0;
    identifyAnonymous(id);
    captureEvent("session_started", {
      session_id: id,
      locale,
      is_embedded: typeof window !== "undefined" ? window.self !== window.top : false,
      referrer: typeof document !== "undefined" ? document.referrer || "" : "",
    });
  }, [locale]);

  // Reset conversation memory when language tab changes
  const prevLocale = useRef(locale);
  useEffect(() => {
    if (prevLocale.current !== locale) {
      prevLocale.current = locale;
      setSessionId((prev) => prev); // keep analytics id; backend session cleared below
      // Clear backend session id by forcing new uuid only for chat API while keeping analytics:
      // product choice: keep same analytics session across locale toggle mid-page.
      // New chat messages will send null backend continuity via reset of chat session field:
      // We null the API session by generating a new chat-only id... Simpler: full reset.
      resetSession();
    }
  }, [locale, resetSession]);

  async function onSubmit(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const sid = sessionId || getSessionId();
    if (!sessionId) setSessionId(sid);

    setError(null);
    setInput("");
    const userMsg: ChatMessage = { id: uid(), role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    const isFirstUser = userTurnCountRef.current === 0;
    userTurnCountRef.current += 1;

    if (isFirstUser) {
      const cat = guessCategory(text);
      categoryRef.current = cat;
      setDiagnosisCategory(cat);
      captureEvent("symptom_entered", {
        session_id: sid,
        symptom_length: text.length,
        symptom_category_guess: cat,
        locale,
      });
    } else if (awaitingClarifyAnswerRef.current) {
      captureEvent("clarifying_question_answered", {
        session_id: sid,
        question_number: lastQuestionNumberRef.current,
        response_length: text.length,
      });
      awaitingClarifyAnswerRef.current = false;
    }

    try {
      const res = await sendChatMessage({
        message: text,
        language: locale,
        sessionId: sid,
        vehicle,
      });
      // Keep client analytics id as source of truth for funnel join
      if (res.vehicle) setVehicle(res.vehicle);

      const assistantMsg: ChatMessage = {
        id: uid(),
        role: "assistant",
        content: res.reply,
        diagnosis: res.diagnosis || null,
        contentHash: res.content_hash || null,
        diagnosisId: res.diagnosis_id || null,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (res.mode === "question") {
        const qNum = Math.max(1, res.questions_asked_count || lastQuestionNumberRef.current + 1);
        lastQuestionNumberRef.current = qNum;
        awaitingClarifyAnswerRef.current = true;
        captureEvent("clarifying_question_shown", {
          session_id: sid,
          question_number: qNum,
          locale,
        });
      }

      if (res.mode === "diagnosis" && res.diagnosis) {
        const cat =
          categoryRef.current !== "other"
            ? categoryRef.current
            : guessCategory(
                res.diagnosis.diagnosis.map((c) => c.cause).join(" ") || text
              );
        categoryRef.current = cat;
        setDiagnosisCategory(cat);
        captureEvent("diagnosis_completed", {
          session_id: sid,
          diagnosis_category: cat,
          estimated_cost_range: res.diagnosis.estimated_cost,
          turns_to_diagnosis: userTurnCountRef.current,
          locale,
        });
        // cta_shown is fired by LeadCapture mount
      }
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

        {messages.map((m, i) => {
          const showLead =
            !!m.diagnosis && !messages.slice(i + 1).some((x) => x.diagnosis);
          return (
            <MessageBubble
              key={m.id}
              message={m}
              sessionId={sessionId}
              locale={locale}
              diagnosisCategory={diagnosisCategory}
              showLead={showLead}
              contentHash={m.contentHash}
            />
          );
        })}

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
