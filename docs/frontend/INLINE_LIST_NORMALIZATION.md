# Inline list normalization (MarkdownRenderer)

## Problem

The LLM often outputs numbered lists inline as a single paragraph:

```
áreas: 1. Crear contenido... . 2. Invertir en... . 3. Crear una comunidad...
```

`react-markdown` + `remark-gfm` requires each list item on its own line to render as `<ol>`. Inline text shows as a plain paragraph, losing visual hierarchy.

## Solution

A `normalizeLists()` function in `MarkdownRenderer.tsx:153` that inserts newlines before inline list markers.

```ts
function normalizeLists(text: string): string {
  return text.replace(/([.!?:;])\s+(\d+[.)]\s)/g, "$1\n$2");
}
```

Regex:
- `([.!?:;])` — sentence-ending punctuation or colon
- `\s+` — whitespace
- `(\d+[.)]\s)` — list marker: digits + `.` or `)` + space

Transforms:
```
áreas: 1. Crear... . 2. Invertir...
```
→
```
áreas:
1. Crear...
2. Invertir...
```

Applied before `ReactMarkdown` render (line 162). Zero backend changes.

## Non-matches (safe)

| Pattern | Why |
|---------|-----|
| `2.0`, `1.5` | No space after period |
| `2024. Luego` | Letter after space, not digit |
| `$1.50`, `v2.0` | No space after period |
| Already formatted `\n` items | Replaces `\n` → `\n` (no-op) |
| `1)` style | Covered by `[.)]` |

## False positives (rare, minor)

- `"punto 5. del manual"` preceded by punctuation → inserts spurious newline. Acceptable trade-off.
