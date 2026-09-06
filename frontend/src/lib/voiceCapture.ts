/** Whisper PCM helpers shared by inline mic and legacy voice recorder. */

export const WHISPER_SAMPLE_RATE = 16000;
export const VOICE_BAR_COUNT = 20;

export function formatRecordingElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const s = Math.floor(totalSeconds % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${s}`;
}

export function resampleToWhisperRate(
  samples: Float32Array,
  sourceRate: number,
): Float32Array {
  if (!sourceRate || sourceRate === WHISPER_SAMPLE_RATE) {
    return samples;
  }
  const ratio = sourceRate / WHISPER_SAMPLE_RATE;
  const outLen = Math.max(1, Math.round(samples.length / ratio));
  const out = new Float32Array(outLen);
  const last = Math.max(0, samples.length - 1);
  for (let i = 0; i < outLen; i += 1) {
    const srcIndex = i * ratio;
    const i0 = Math.min(last, Math.floor(srcIndex));
    const i1 = Math.min(last, i0 + 1);
    const frac = srcIndex - i0;
    out[i] = (samples[i0] ?? 0) * (1 - frac) + (samples[i1] ?? 0) * frac;
  }
  return out;
}

export function encodeWavBlob(
  channelData: Float32Array[],
  sampleRate: number,
): Blob {
  const length = channelData.reduce((sum, chunk) => sum + chunk.length, 0);
  const concatenated = new Float32Array(length);
  let offset = 0;
  for (const chunk of channelData) {
    concatenated.set(chunk, offset);
    offset += chunk.length;
  }
  const samples = resampleToWhisperRate(concatenated, sampleRate);
  const outRate = WHISPER_SAMPLE_RATE;

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
  view.setUint32(24, outRate, true);
  view.setUint32(28, outRate * 2, true);
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

export async function unlockAudioContext(ctx: AudioContext): Promise<void> {
  if (ctx.state === "suspended") {
    await ctx.resume();
  }
  if (ctx.state !== "running") {
    await ctx.resume();
  }
}

export function micPermissionHelpMessage(): string {
  const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
  const isIOS = /iPad|iPhone|iPod/i.test(ua);
  const isAndroid = /Android/i.test(ua);

  if (isIOS) {
    return (
      "Microphone access is blocked. On iPhone/iPad: open Settings → Privacy & Security → " +
      "Microphone → enable this app (or Safari → site settings for this page), then return and tap the mic again."
    );
  }
  if (isAndroid) {
    return (
      "Microphone access is blocked. On Android: open Settings → Apps → this app → Permissions → " +
      "Microphone → Allow, then return and tap the mic again."
    );
  }
  return (
    "Microphone access is blocked at the browser or device level. Open your site/app permissions, " +
    "allow the microphone, then tap the mic again."
  );
}
