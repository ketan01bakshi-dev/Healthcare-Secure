"use client";

import { useCallback } from "react";

import { useVoiceTranscription, type SpeakLanguage } from "@/hooks/useVoiceTranscription";
import { formatRecordingElapsed, micPermissionHelpMessage } from "@/lib/voiceCapture";
import { useI18n } from "@/lib/i18n";
import ThemedSelect from "@/components/ThemedSelect";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onDictation?: (text: string, meta?: { language?: SpeakLanguage }) => void;
  disabled?: boolean;
  label?: string;
  placeholder?: string;
  id?: string;
  minRows?: number;
};

function MicIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      className={className}
      fill="currentColor"
      viewBox="0 0 24 24"
    >
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z" />
    </svg>
  );
}

export default function ClinicalNoteInput({
  value,
  onChange,
  onDictation,
  disabled = false,
  label,
  placeholder,
  id = "clinical-note",
  minRows = 4,
}: Props) {
  const { t } = useI18n();

  const handleTranscript = useCallback(
    (text: string, meta?: { language?: SpeakLanguage }) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      onChange(value.trim() ? `${value.trim()}\n${trimmed}` : trimmed);
      onDictation?.(trimmed, meta);
    },
    [onChange, onDictation, value],
  );

  const voice = useVoiceTranscription({
    disabled,
    onTranscript: handleTranscript,
  });

  const statusLine = voice.isUploading
    ? t("voiceTranscribing")
    : voice.isRecording
      ? `${t("recording")} ${formatRecordingElapsed(voice.elapsed)}`
      : voice.message;

  return (
    <div className="space-y-2">
      {label ? (
        <label className="block text-xs font-medium text-slate-600" htmlFor={id}>
          {label}
        </label>
      ) : null}

      <div
        className={`overflow-hidden rounded-2xl border bg-white transition-shadow ${
          voice.isRecording
            ? "border-clinical-500 ring-2 ring-clinical-500/25"
            : "border-slate-200 focus-within:border-slate-300 focus-within:ring-2 focus-within:ring-slate-200"
        }`}
      >
        <textarea
          className="block w-full resize-y border-0 bg-transparent px-4 pb-2 pt-3 text-sm leading-relaxed text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60"
          disabled={disabled || voice.busy}
          id={id}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={minRows}
          value={value}
        />

        <div className="flex items-center gap-2 border-t border-slate-100 px-2 py-2">
          <div className="min-w-0 flex-1">
            <ThemedSelect
              aria-label={t("voiceSpeakLanguage")}
              className="!mt-0 h-9 min-h-9 rounded-full border-0 bg-slate-100 !ring-0 focus:!ring-0"
              disabled={disabled || voice.busy}
              id={`${id}-lang`}
              onChange={(v) => voice.setSpeakLanguage(v as SpeakLanguage)}
              options={[
                { value: "auto", label: t("voiceLangAuto") },
                { value: "en", label: t("voiceLangEnglish") },
                { value: "hi", label: t("voiceLangHindi") },
              ]}
              value={voice.speakLanguage}
            />
          </div>

          <button
            aria-label={
              voice.isRecording ? t("stop") : t("clinicalNoteDictate")
            }
            aria-pressed={voice.isRecording}
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 ${
              voice.isRecording
                ? "bg-red-600 shadow-[0_0_0_4px_rgba(220,38,38,0.2)]"
                : voice.isUploading
                  ? "bg-slate-700"
                  : "bg-slate-900"
            }`}
            disabled={disabled || voice.isUploading}
            onClick={voice.toggleRecording}
            type="button"
          >
            {voice.isUploading ? (
              <span
                aria-hidden
                className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"
              />
            ) : (
              <MicIcon className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>

      {statusLine ? (
        <p
          aria-live="polite"
          className={`min-h-[1rem] text-xs ${
            voice.status === "error"
              ? "text-red-600"
              : voice.status === "success"
                ? "text-emerald-700"
                : "text-slate-500"
          }`}
          role="status"
        >
          {statusLine}
        </p>
      ) : null}

      {voice.showMicHelp ? (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-3 py-3 text-left"
          role="alert"
        >
          <p className="text-sm font-medium text-red-900">
            {t("voiceMicBlockedTitle")}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-red-800">
            {micPermissionHelpMessage()}
          </p>
          <button
            className="mt-3 min-h-10 rounded-lg bg-red-600 px-3 text-sm font-medium text-white"
            onClick={() => voice.setShowMicHelp(false)}
            type="button"
          >
            {t("voiceMicHelpDismiss")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
