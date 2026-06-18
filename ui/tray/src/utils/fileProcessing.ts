export const TEXT_MIME_TYPES = new Set([
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "text/x-python",
  "text/javascript",
  "text/typescript",
  "text/x-java",
  "text/x-c",
  "text/x-cpp",
  "text/yaml",
  "text/xml",
]);

export const TEXT_EXTENSIONS = new Set([
  ".txt",
  ".md",
  ".csv",
  ".json",
  ".py",
  ".js",
  ".ts",
  ".tsx",
  ".jsx",
  ".html",
  ".css",
  ".xml",
  ".yaml",
  ".yml",
]);

export const MAX_IMAGE_DIM = 1024;
export const JPEG_QUALITY = 0.85;

export function hasExtension(file: File, extensions: Set<string>): boolean {
  const lowerName = file.name.toLowerCase();
  for (const ext of extensions) {
    if (lowerName.endsWith(ext)) return true;
  }
  return false;
}

export function isTextLikeFile(file: File): boolean {
  return TEXT_MIME_TYPES.has(file.type) || file.type.startsWith("text/") || hasExtension(file, TEXT_EXTENSIONS);
}

export function isImageLikeFile(file: File): boolean {
  return file.type.startsWith("image/");
}

export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = typeof reader.result === "string" ? reader.result : "";
      resolve(value.includes(",") ? value.split(",", 2)[1] ?? "" : value);
    };
    reader.onerror = () => reject(reader.error ?? new Error(`Failed to read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

export function resizeImage(
  dataUrl: string,
  maxDim: number = MAX_IMAGE_DIM,
  quality: number = JPEG_QUALITY,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      let { width, height } = img;
      const scale = maxDim / Math.max(width, height);
      if (scale >= 1) {
        resolve(dataUrl.split(",", 2)[1] ?? "");
        return;
      }
      width = Math.round(width * scale);
      height = Math.round(height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) { resolve(dataUrl.split(",", 2)[1] ?? ""); return; }
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL("image/jpeg", quality).split(",", 2)[1] ?? "");
    };
    img.onerror = () => reject(new Error("Failed to decode image"));
    img.src = dataUrl;
  });
}

import type { FileAttachment } from "../api/types";

export async function buildLocalAttachment(file: File): Promise<FileAttachment | null> {
  if (isTextLikeFile(file)) {
    return {
      filename: file.name,
      mime_type: file.type || "text/plain",
      content: await file.text(),
      type: "text",
    };
  }

  if (isImageLikeFile(file)) {
    const raw = await readFileAsDataUrl(file);
    const dataUrl = `data:${file.type};base64,${raw}`;
    const resized = await resizeImage(dataUrl);
    return {
      filename: file.name,
      mime_type: "image/jpeg",
      content: resized,
      type: "image",
    };
  }

  return null;
}
