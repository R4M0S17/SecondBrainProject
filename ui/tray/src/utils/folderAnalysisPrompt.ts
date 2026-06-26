import type { TFunction } from "i18next";

export type AnalysisMode = "structure" | "content" | "full";

export function buildFolderAnalysisPrompt(
  mode: AnalysisMode,
  path: string,
  locale: string,
  t: TFunction,
): string {
  switch (mode) {
    case "structure":
      return t("folder.prompt_structure", { path, locale });
    case "content":
      return t("folder.prompt_content", { path, locale });
    case "full":
      return t("folder.prompt_full", { path, locale });
  }
}
