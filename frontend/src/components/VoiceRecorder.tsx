"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/doctorSession";

type RecorderStatus = "idle" | "recording" | "uploading" | "success" | "error";

const BAR_COUNT = 20;

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const s = Math.floor(totalSeconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

function micPermissionHelpMessage(): string {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const isIOS = /iPad|iPhone|iPod/i.test(ua);
  const isAndroid = /Android/i.test(ua);

  if (isIOS) {
    return (
      "Microphone access is blocked. On iPhone/iPad: open Settings → Privacy & Security → " +
      "Microphone → enable this app (or Safari → site settings for this page), then return and tap Record again."
    );
  }
  if (isAndroid) {
    return (
      "Microphone access is blocked. On Android: open Settings → Apps → this app → Permissions → " +
      "Microphone → Allow, then return and tap Record again."
    );
  }
  return (
    "Microphone access is blocked at the browser or device level. Open your site/app permissions, " +
    "allow the microphone, then tap Record again."
  );
}

/** Encode in-memory PCM float samples as a WAV Blob (never written to disk/storage). */
function encodeWavBlob(
  channelData: Float32Array[],
  sampleRate: number,
): Blob {
  const length = channelData.reduce((sum, chunk) => sum + chunk.length, 0);
  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of channelData) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }

  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  const writeString = (pos: number, str: string) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(pos + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let cursor = 44;
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i] ?? 0));
    view.setInt16(
      cursor,
      clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff,
      true,
    );
    cursor += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

async function unlockAudioContext(ctx: AudioContext): Promise<void> {
  // Mobile Safari/Chrome require a user-gesture resume; tap Record satisfies that.
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
  // Nudge the graph awake on some WebViews.
  if (ctx.state !== "running") {
    await ctx.resume();
  }
}

export default function VoiceRecorder({
  onTranscript,
  disabled = false,
}: {
  onTranscript?: (text: string) => void;
  disabled?: boolean;
}) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [levels, setLevels] = useState<number[]>(() =>
    Array.from({ length: BAR_COUNT }, () => 0.08),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [showMicHelp, setShowMicHelp] = useState(false);

  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const rafRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);

  const clearTimerAndRaf = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const teardownGraph = useCallback(() => {
    clearTimerAndRaf();

    try {
      processorRef.current?.disconnect();
    } catch {
      /* already disconnected */
    }
    try {
      sourceRef.current?.disconnect();
    } catch {
      /* already disconnected */
    }
    try {
      analyserRef.current?.disconnect();
    } catch {
      /* already disconnected */
    }

    processorRef.current = null;
    sourceRef.current = null;
    analyserRef.current = null;

    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;

    void audioContextRef.current?.close();
    audioContextRef.current = null;
    chunksRef.current = [];
  }, [clearTimerAndRaf]);

  useEffect(() => () => teardownGraph(), [teardownGraph]);

  const animateWave = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(data);
      const next: number[] = [];
      const step = Math.max(1, Math.floor(data.length / BAR_COUNT));
      for (let i = 0; i < BAR_COUNT; i += 1) {
        const value = data[i * step] ?? 0;
        next.push(Math.max(0.08, value / 255));
      }
      setLevels(next);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  const uploadBlob = useCallback(async (blob: Blob) => {
    setStatus("uploading");
    setMessage("Converting speech to text…");
    setTranscript(null);

    const form = new FormData();
    form.append("audio", blob, "prescription.wav");

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 180000);

    try {
      const response = await apiFetch("/api/v1/prescription/transcribe", {
        method: "POST",
        body: form,
        signal: controller.signal,
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Upload failed (${response.status})`);
      }

      const data = (await response.json()) as {
        transcript?: string;
        message?: string;
        provider?: string;
      };
      const text = (data.transcript ?? "").trim();
      setStatus("success");
      setTranscript(text || null);
      setMessage(
        text
          ? "Voice note added."
          : data.message || "No speech detected. Try again.",
      );
      if (text) {
        onTranscript?.(text);
      }
    } catch (err) {
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      setStatus("error");
      setMessage(
        isAbort
          ? "That took too long. Try a shorter recording."
          : err instanceof Error
            ? err.message
            : "Failed to upload recording.",
      );
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, [onTranscript]);

  const stopRecording = useCallback(async () => {
    const ctx = audioContextRef.current;
    const chunks = chunksRef.current.slice();
    const sampleRate = ctx?.sampleRate ?? 44100;

    teardownGraph();
    setLevels(Array.from({ length: BAR_COUNT }, () => 0.08));

    if (chunks.length === 0) {
      setStatus("error");
      setMessage("No audio captured.");
      return;
    }

    const blob = encodeWavBlob(chunks, sampleRate);
    chunks.length = 0;
    chunksRef.current = [];

    await uploadBlob(blob);
  }, [teardownGraph, uploadBlob]);

  const startRecording = useCallback(async () => {
    setMessage(null);
    setTranscript(null);
    setShowMicHelp(false);
    setElapsed(0);
    chunksRef.current = [];

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw Object.assign(new Error("getUserMedia_unavailable"), {
          name: "NotSupportedError",
        });
      }

      // Create + unlock AudioContext inside the tap gesture (required on iOS/Android).
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      const ctx = new AudioCtx();
      audioContextRef.current = ctx;
      await unlockAudioContext(ctx);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
        },
        video: false,
      });

      // Some mobile browsers suspend again after GUM — re-unlock.
      await unlockAudioContext(ctx);

      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.7;

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        chunksRef.current.push(new Float32Array(input));
      };

      source.connect(analyser);
      source.connect(processor);
      const mute = ctx.createGain();
      mute.gain.value = 0;
      processor.connect(mute);
      mute.connect(ctx.destination);

      streamRef.current = stream;
      sourceRef.current = source;
      analyserRef.current = analyser;
      processorRef.current = processor;
      startedAtRef.current = Date.now();

      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 250);

      setStatus("recording");
      animateWave();
    } catch (err) {
      const e = err as { name?: string; message?: string };
      teardownGraph();
      setStatus("error");

      const denied =
        e?.name === "NotAllowedError" ||
        e?.name === "PermissionDeniedError" ||
        /permission|denied|notallowed/i.test(e?.message ?? "");

      if (denied) {
        setShowMicHelp(true);
        setMessage("Microphone permission is turned off for this app.");
      } else if (e?.name === "NotFoundError") {
        setMessage("No microphone was found on this device.");
      } else if (e?.name === "NotSupportedError" || e?.name === "SecurityError") {
        setMessage(
          "Microphone is blocked. Please allow microphone access and try again.",
        );
      } else {
        setMessage("Microphone access denied or unavailable.");
      }
    }
  }, [animateWave, teardownGraph]);

  const onToggle = useCallback(() => {
    if (disabled || status === "uploading") return;
    if (status === "recording") {
      void stopRecording();
      return;
    }
    void startRecording();
  }, [disabled, status, startRecording, stopRecording]);

  const isRecording = status === "recording";
  const isUploading = status === "uploading";
  const buttonLabel = isUploading
    ? "Transcribing…"
    : isRecording
      ? "Stop"
      : "Record";

  return (
    <section
      aria-label="Prescription voice recorder"
      className="mx-auto w-full max-w-md overflow-x-hidden rounded-2xl border border-clinical-100/15 bg-clinical-900/40 px-4 py-6 shadow-lg backdrop-blur-sm sm:px-6 sm:py-8"
    >
      <header className="mb-6 text-center sm:mb-8">
        <h2 className="text-lg font-semibold tracking-tight text-clinical-50 sm:text-xl">
          Voice prescription
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-clinical-100/70">
          Tap Record, speak clearly, then tap Stop.
        </p>
      </header>

      <div
        aria-hidden={!isRecording}
        className="mb-5 flex h-14 max-w-full items-end justify-center gap-0.5 overflow-hidden sm:mb-6 sm:h-20 sm:gap-1.5"
      >
        {levels.map((level, index) => (
          <span
            key={index}
            className={`w-1.5 max-w-[6px] flex-1 rounded-full transition-[height,background-color] duration-75 sm:w-2 sm:flex-none ${
              isRecording ? "bg-clinical-500" : "bg-clinical-100/25"
            }`}
            style={{
              height: `${Math.round(level * 100)}%`,
              opacity: isRecording ? 0.55 + level * 0.45 : 0.35,
            }}
          />
        ))}
      </div>

      <div className="mb-6 flex min-h-12 items-center justify-center">
        <time
          aria-live="polite"
          className={`font-mono text-3xl tabular-nums tracking-wider sm:text-4xl ${
            isRecording ? "text-clinical-50" : "text-clinical-100/50"
          }`}
          dateTime={`PT${elapsed}S`}
        >
          {formatElapsed(elapsed)}
        </time>
      </div>

      <div className="flex justify-center px-2">
        <button
          aria-pressed={isRecording}
          className={`relative flex h-14 w-14 min-h-12 min-w-12 touch-manipulation items-center justify-center rounded-full text-sm font-semibold text-white transition active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-clinical-100 disabled:cursor-not-allowed disabled:opacity-60 sm:h-28 sm:w-28 sm:text-base ${
            isRecording
              ? "bg-red-600 shadow-[0_0_0_6px_rgba(220,38,38,0.25)] active:bg-red-700"
              : isUploading
                ? "bg-clinical-700"
                : "bg-clinical-500 active:bg-clinical-700"
          }`}
          disabled={isUploading || disabled}
          onClick={onToggle}
          type="button"
        >
          {isUploading ? (
            <span
              aria-hidden
              className="absolute inset-3 animate-spin rounded-full border-2 border-white/30 border-t-white"
            />
          ) : null}
          <span className={isUploading ? "opacity-0" : undefined}>
            {buttonLabel}
          </span>
        </button>
      </div>

      <p
        aria-live="polite"
        className={`mt-5 min-h-[1.25rem] break-words text-center text-sm ${
          status === "error"
            ? "text-red-300"
            : status === "success"
              ? "text-clinical-100"
              : "text-clinical-100/60"
        }`}
      >
        {isUploading
          ? "Converting speech to text…"
          : (message ?? "\u00a0")}
      </p>

      {showMicHelp ? (
        <div
          className="mt-4 rounded-xl border border-red-400/30 bg-red-950/40 px-4 py-4 text-left shadow-lg"
          role="alert"
        >
          <p className="text-sm font-semibold text-red-100">
            Enable microphone in phone settings
          </p>
          <p className="mt-2 text-sm leading-relaxed text-red-100/85">
            {micPermissionHelpMessage()}
          </p>
          <button
            className="mt-4 inline-flex min-h-12 min-w-12 items-center justify-center rounded-lg bg-red-600 px-4 text-sm font-medium text-white active:bg-red-700"
            onClick={() => setShowMicHelp(false)}
            type="button"
          >
            Got it
          </button>
        </div>
      ) : null}

      {transcript ? (
        <div className="mt-4 max-w-full overflow-hidden rounded-lg border border-clinical-100/15 bg-black/20 px-4 py-3 text-left">
          <p className="text-xs uppercase tracking-wide text-clinical-100/55">
            What you said
          </p>
          <p className="mt-1 break-words text-sm leading-relaxed text-clinical-50">
            {transcript}
          </p>
        </div>
      ) : null}
    </section>
  );
}
