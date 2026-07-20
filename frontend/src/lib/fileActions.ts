import { Directory, Filesystem } from "@capacitor/filesystem";
import { Share } from "@capacitor/share";
import { FileOpener } from "@capacitor-community/file-opener";

function isCapacitorRuntime(): boolean {
  const cap = (window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } })
    .Capacitor;
  if (!cap) return false;
  try {
    return typeof cap.isNativePlatform === "function"
      ? cap.isNativePlatform()
      : true;
  } catch {
    return true;
  }
}

async function blobToBase64(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function writeCacheFile(blob: Blob, filename: string): Promise<string> {
  const safeName = filename.replace(/[^\w.\- ]+/g, "_") || "attachment";
  const base64 = await blobToBase64(blob);
  const path = `healthcare/${Date.now()}-${safeName}`;
  await Filesystem.writeFile({
    path,
    data: base64,
    directory: Directory.Cache,
    recursive: true,
  });
  const { uri } = await Filesystem.getUri({
    path,
    directory: Directory.Cache,
  });
  return uri;
}

/** Open a PDF/image with the system viewer on Capacitor; falls back to share. */
export async function openAttachmentNative(
  blob: Blob,
  filename: string,
): Promise<"opened" | "shared"> {
  const type = blob.type || "application/octet-stream";
  const safeName = filename.replace(/[^\w.\- ]+/g, "_") || "attachment";

  if (isCapacitorRuntime()) {
    const uri = await writeCacheFile(blob, safeName);
    try {
      await FileOpener.open({
        filePath: uri,
        contentType: type,
        openWithDefault: true,
      });
      return "opened";
    } catch {
      await Share.share({
        title: safeName,
        text: safeName,
        url: uri,
        dialogTitle: "Open or save attachment",
      });
      return "shared";
    }
  }

  await shareOrDownloadBlob(blob, safeName);
  return "shared";
}

/** Share/save a blob via Capacitor Share or Web Share (Android-safe). */
export async function shareOrDownloadBlob(
  blob: Blob,
  filename: string,
): Promise<"shared" | "downloaded"> {
  const type = blob.type || "application/octet-stream";
  const safeName = filename.replace(/[^\w.\- ]+/g, "_") || "attachment";

  if (isCapacitorRuntime()) {
    const uri = await writeCacheFile(blob, safeName);
    await Share.share({
      title: safeName,
      text: safeName,
      url: uri,
      dialogTitle: "Save or open attachment",
    });
    return "shared";
  }

  const file = new File([blob], safeName, { type });
  const canShareFiles =
    typeof navigator !== "undefined" &&
    typeof navigator.canShare === "function" &&
    navigator.canShare({ files: [file] });

  if (canShareFiles) {
    await navigator.share({ files: [file], title: safeName });
    return "shared";
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = safeName;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return "downloaded";
}

export type ViewerPayload = {
  url: string;
  mime: string;
  filename: string;
  kind: "image" | "pdf" | "other";
};

export function blobToViewerPayload(
  blob: Blob,
  filename: string,
): ViewerPayload {
  const mime = blob.type || "application/octet-stream";
  const url = URL.createObjectURL(blob);
  let kind: ViewerPayload["kind"] = "other";
  if (mime.startsWith("image/")) kind = "image";
  else if (mime === "application/pdf" || filename.toLowerCase().endsWith(".pdf"))
    kind = "pdf";
  return { url, mime, filename, kind };
}

/** Open system print dialog for a blob (PDF/image). */
export async function printAttachmentBlob(
  blob: Blob,
  filename: string,
): Promise<void> {
  const url = URL.createObjectURL(blob);
  try {
    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "0";
    iframe.src = url;
    document.body.appendChild(iframe);
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(
        () => reject(new Error("Print timed out")),
        15000,
      );
      iframe.onload = () => {
        window.clearTimeout(timer);
        try {
          iframe.contentWindow?.focus();
          iframe.contentWindow?.print();
        } catch (err) {
          reject(err instanceof Error ? err : new Error("Print failed"));
          return;
        }
        resolve();
      };
    });
    window.setTimeout(() => {
      document.body.removeChild(iframe);
      URL.revokeObjectURL(url);
    }, 60_000);
  } catch {
    URL.revokeObjectURL(url);
    await openAttachmentNative(blob, filename);
  }
}
