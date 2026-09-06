"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/doctorSession";
import {
  encodeWavBlob,
  unlockAudioContext,
  WHISPER_SAMPLE_RATE,
} from "@/lib/voiceCapture";

export type SpeakLanguage = "en" | "hi" | "auto";
type RecorderStatus = "idle" | "recording" | "uploading" | "success" | "error";

type UseVoiceTranscriptionOptions = {
  disabled?: boolean;
  onTranscript?: (text: string, meta?: { language?: SpeakLanguage }) => void;
};

export function useVoiceTranscription({
  disabled = false,
  onTranscript,
}: UseVoiceTranscriptionOptions) {
  const [speakLanguage, setSpeakLanguage] = useState<SpeakLanguage>("auto");
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [showMicHelp, setShowMicHelp] = useState(false);

  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const chunksRef = useRef<Float32Array[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const teardownGraph = useCallback(() => {
    clearTimer();
    try {
      processorRef.current?.disconnect();
    } catch {
      /* disconnected */
    }
    try {
      sourceRef.current?.disconnect();
    } catch {
      /* disconnected */
    }
    processorRef.current = null;
    sourceRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
    chunksRef.current = [];
  }, [clearTimer]);

  useEffect(() => () => teardownGraph(), [teardownGraph]);

  const uploadBlob = useCallback(
    async (blob: Blob) => {
      setStatus("uploading");
      setMessage(null);

      const form = new FormData();
      form.append("audio", blob, "clinical-note.wav");
      form.append("language", speakLanguage);

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
        };
        const text = (data.transcript ?? "").trim();
        setStatus(text ? "success" : "error");
        setMessage(data.message || (text ? null : "No speech detected."));
        if (text) {
          onTranscript?.(text, { language: speakLanguage });
        }
      } catch (err) {
        const isAbort = err instanceof DOMException && err.name === "AbortError";
        setStatus("error");
        setMessage(
          isAbort
            ? "Transcription timed out."
            : err instanceof Error
              ? err.message
              : "Upload failed.",
        );
      } finally {
        window.clearTimeout(timeoutId);
      }
    },
    [onTranscript, speakLanguage],
  );

  const stopRecording = useCallback(async () => {
    const ctx = audioContextRef.current;
    const chunks = chunksRef.current.slice();
    const sampleRate = ctx?.sampleRate ?? 44100;
    teardownGraph();

    if (chunks.length === 0) {
      setStatus("error");
      setMessage("No audio captured.");
      return;
    }

    const blob = encodeWavBlob(chunks, sampleRate);
    await uploadBlob(blob);
  }, [teardownGraph, uploadBlob]);

  const startRecording = useCallback(async () => {
    if (disabled) return;
    setMessage(null);
    setShowMicHelp(false);
    setElapsed(0);
    chunksRef.current = [];

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw Object.assign(new Error("getUserMedia_unavailable"), {
          name: "NotSupportedError",
        });
      }

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;
      let ctx: AudioContext;
      try {
        ctx = new AudioCtx({ sampleRate: WHISPER_SAMPLE_RATE });
      } catch {
        ctx = new AudioCtx();
      }
      audioContextRef.current = ctx;
      await unlockAudioContext(ctx);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          channelCount: 1,
          sampleRate: WHISPER_SAMPLE_RATE,
        },
        video: false,
      });
      await unlockAudioContext(ctx);

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0);
        chunksRef.current.push(new Float32Array(input));
      };

      source.connect(processor);
      const mute = ctx.createGain();
      mute.gain.value = 0;
      processor.connect(mute);
      mute.connect(ctx.destination);

      streamRef.current = stream;
      sourceRef.current = source;
      processorRef.current = processor;
      startedAtRef.current = Date.now();

      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 250);

      setStatus("recording");
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
      } else {
        setMessage("Microphone access denied or unavailable.");
      }
    }
  }, [disabled, teardownGraph]);

  const toggleRecording = useCallback(() => {
    if (disabled || status === "uploading") return;
    if (status === "recording") {
      void stopRecording();
      return;
    }
    void startRecording();
  }, [disabled, startRecording, status, stopRecording]);

  const isRecording = status === "recording";
  const isUploading = status === "uploading";
  const busy = isRecording || isUploading;

  return {
    speakLanguage,
    setSpeakLanguage,
    status,
    elapsed,
    message,
    showMicHelp,
    setShowMicHelp,
    toggleRecording,
    isRecording,
    isUploading,
    busy,
  };
}
