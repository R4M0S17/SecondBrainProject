import type { TFunction } from "i18next";
import type { DocumentChunkHit } from "../api/types";

export function buildDocumentSearchPrompt(
  query: string,
  hits: DocumentChunkHit[],
  locale: string,
  t: TFunction,
  includeAnswer?: string | null,
): string {
  const lines: string[] = [];

  lines.push(t("search_docs.prompt_header", { query }));
  lines.push("");

  if (includeAnswer) {
    lines.push(t("search_docs.prompt_prev_answer"), includeAnswer, "");
  }

  lines.push(t("search_docs.prompt_chunks_header"));
  for (let i = 0; i < hits.length; i++) {
    const h = hits[i];
    lines.push(`${i + 1}. [${h.filename}, ${t("search_docs.chunk_label", { n: h.chunk_index })}]: "${h.snippet}"`);
  }

  lines.push("", t("search_docs.prompt_instruction", { locale }));
  return lines.join("\n");
}
