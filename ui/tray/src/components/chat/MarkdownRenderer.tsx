import { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Components } from "react-markdown";
import { Check, Copy } from "lucide-react";

function CodeBlock({ language, code }: { language: string; code: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard not available
    }
  };

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden border border-white/5">
      <div className="flex items-center justify-between px-4 py-1.5 bg-[#282c34]">
        <span className="text-[11px] text-gray-400 uppercase tracking-wider font-medium">
          {language || "code"}
        </span>
        <button
          onClick={handleCopy}
          className="text-gray-400 hover:text-white transition-colors p-1 rounded opacity-0 group-hover:opacity-100 focus:opacity-100"
          aria-label={t("markdown.copy_code")}
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language || undefined}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          borderBottomLeftRadius: "0.5rem",
          borderBottomRightRadius: "0.5rem",
          fontSize: "13px",
          lineHeight: "1.5",
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

const components: Components = {
  pre: ({ children }) => <>{children}</>,

  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const codeStr = String(children).replace(/\n$/, "");

    if (!match && !codeStr.includes("\n")) {
      return (
        <code
          className="bg-surface-container-high text-primary-fixed px-1.5 py-0.5 rounded text-[13px] font-mono break-words"
          {...props}
        >
          {children}
        </code>
      );
    }

    return <CodeBlock language={match?.[1] || ""} code={codeStr} />;
  },

  h1: ({ children }) => (
    <h1 className="text-lg font-bold text-on-surface mt-4 mb-2 leading-snug">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-bold text-on-surface mt-3 mb-2 leading-snug">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-on-surface mt-3 mb-1 leading-snug">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-semibold text-on-surface mt-2 mb-1 leading-snug">{children}</h4>
  ),

  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,

  ul: ({ children }) => (
    <ul className="list-disc list-outside pl-5 mb-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-outside pl-5 mb-2 space-y-1">{children}</ol>
  ),
  li: ({ children }) => <li className="text-sm">{children}</li>,

  strong: ({ children }) => (
    <strong className="font-semibold text-on-surface">{children}</strong>
  ),

  a: ({ href, children }) => (
    <a
      href={href}
      className="text-primary underline underline-offset-2 hover:text-primary-fixed transition-colors"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),

  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-primary-container pl-4 italic text-on-surface-variant/80 my-2">
      {children}
    </blockquote>
  ),

  hr: () => <hr className="border-outline-variant/30 my-4" />,

  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-outline-variant/30">
      <table className="min-w-full border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-surface-container-high">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b border-outline-variant/20 last:border-b-0 even:bg-surface-container-low">
      {children}
    </tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left text-xs font-semibold text-on-surface">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-sm text-on-surface-variant">{children}</td>
  ),

  img: ({ src, alt }) => (
    <img src={src} alt={alt || ""} className="max-w-full rounded-lg my-2" loading="lazy" />
  ),
};

function normalizeLists(text: string): string {
  return text.replace(/([.!?:;])\s+(\d+[.)]\s)/g, "$1\n$2");
}

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const normalized = normalizeLists(content);
  return (
    <div className="text-sm text-on-surface-variant">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
