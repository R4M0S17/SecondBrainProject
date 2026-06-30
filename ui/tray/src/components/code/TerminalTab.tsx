import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useChatStore } from "../../stores/chat";
import { useTabStore } from "../../stores/tab";

export default function TerminalTab() {
  const { t } = useTranslation();
  const setPendingChatAction = useChatStore((s) => s.setPendingChatAction);
  const setTab = useTabStore((s) => s.setTab);
  const [terminalReady, setTerminalReady] = useState(false);
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const [shellAvailable, setShellAvailable] = useState<boolean | null>(null);
  const [fallbackOutput, setFallbackOutput] = useState("");
  const [cmdInput, setCmdInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [lastCmdOutput, setLastCmdOutput] = useState<{ cmd: string; output: string } | null>(null);
  const [termStatus, setTermStatus] = useState({ cwd: "~", exitCode: null as number | null, cmdCount: 0 });
  const terminalRef = useRef<HTMLDivElement>(null);
  const fitAddon = useRef<import("@xterm/addon-fit").FitAddon | null>(null);

  useEffect(() => {
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    let xtermEl: Element | null = null;
    const onSelectStart = (e: Event) => e.preventDefault();
    async function initTerminal() {
      try {
        const [{ Terminal }, { FitAddon }] = await Promise.all([
          import("@xterm/xterm"),
          import("@xterm/addon-fit"),
        ]);
      if (cancelled || !terminalRef.current) return;

      const fit = new FitAddon();
      const term = new Terminal({
        theme: {
          background: "#0e0e12",
          foreground: "#e4e1e7",
          cursor: "#2563eb",
          cursorAccent: "#0e0e12",
          selectionBackground: "rgba(59,130,246,0.6)",
          selectionInactiveBackground: "rgba(59,130,246,0.4)",
          black: "#131317",
          red: "#f87171",
          green: "#4ade80",
          yellow: "#e8c423",
          blue: "#60a5fa",
          magenta: "#c0c1ff",
          cyan: "#67e8f9",
          white: "#e4e1e7",
          brightBlack: "#39393d",
          brightRed: "#fca5a5",
          brightGreen: "#86efac",
          brightYellow: "#fde68a",
          brightBlue: "#93c5fd",
          brightMagenta: "#ddd6fe",
          brightCyan: "#67e8f9",
          brightWhite: "#ffffff",
        },
        fontSize: 13,
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        cursorBlink: true,
        cursorStyle: "bar",
        allowTransparency: true,
        scrollback: 5000,
        smoothScrollDuration: 80,
      });

      term.loadAddon(fit);
      fitAddon.current = fit;

      term.open(terminalRef.current);

      xtermEl = terminalRef.current.querySelector(".xterm");
      xtermEl?.addEventListener("selectstart", onSelectStart);

      term.onSelectionChange(() => {
        const selection = term.getSelection();
        if (selection) {
          if (!selection.trim()) {
            term.clearSelection();
            return;
          }
          navigator.clipboard.writeText(selection);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }
      });

      const doFit = () => {
        fit.fit();
        if (term.rows > 2) {
          term.resize(term.cols, term.rows - 1);
        }
      };

      requestAnimationFrame(doFit);

      resizeObserver = new ResizeObserver(() => {
        try { doFit(); } catch { /* ignore */ }
      });
      resizeObserver.observe(terminalRef.current);

      let lineBuf = "";
      let showPrompt = true;
      let cwd = "";

      const history: string[] = [];
      let historyIndex = -1;
      let savedLine = "";

      try {
        const { Command } = await import("@tauri-apps/plugin-shell");
        const r = await Command.create("zsh", ["-c", "echo $HOME"]).execute();
        if (r.stdout) cwd = r.stdout.trim();
      } catch {}

      const executeCmd = async (cmd: string) => {
        let outputBuf = "";
        if (cmd && (history.length === 0 || history[history.length - 1] !== cmd)) {
          history.push(cmd);
          if (history.length > 200) history.shift();
        }
        historyIndex = -1;
        savedLine = "";
        try {
          const { Command } = await import("@tauri-apps/plugin-shell");
          const fullCmd = cwd ? `cd "${cwd}" && ${cmd}` : cmd;
          const result = await Command.create("zsh", ["-c", fullCmd]).execute();
          if (result.stdout) {
            outputBuf += result.stdout;
            term.write(result.stdout.replace(/\n/g, "\r\n"));
          }
          if (result.stderr) {
            outputBuf += result.stderr;
            term.write(`\x1b[31m${result.stderr.replace(/\n/g, "\r\n")}\x1b[0m`);
          }
          if (result.code !== 0 && result.code !== null) {
            outputBuf += `[exit code: ${result.code}]`;
            term.write(`\r\n\x1b[33m[exit code: ${result.code}]\x1b[0m`);
          }
          setTermStatus((s) => ({
            cwd: cwd || "~",
            exitCode: result.code,
            cmdCount: s.cmdCount + 1,
          }));
          if (cmd === "cd" || cmd.startsWith("cd ")) {
            const dir = cmd === "cd" ? "~" : cmd.slice(3).trim() || "~";
            try {
              const q = dir === "~" ? "~" : `"${dir}"`;
              const r = await Command.create("zsh", ["-c", `cd "${cwd}" && cd ${q} && pwd`]).execute();
              if (r.stdout) cwd = r.stdout.trim();
            } catch {}
          }
        } catch {
          term.write(`\r\n\x1b[31m[error]\x1b[0m`);
          setTermStatus((s) => ({
            cwd: cwd || "~",
            exitCode: -1,
            cmdCount: s.cmdCount + 1,
          }));
        }
        term.write(`\r\n\x1b[32m${cwd || "~"}\x1b[0m $ `);
        showPrompt = false;
        term.scrollToBottom();
        setLastCmdOutput({ cmd, output: outputBuf });
      };

      term.onData((data) => {
        term.scrollToBottom();
        if (showPrompt) {
          term.write(`\x1b[32m${cwd || "~"}\x1b[0m $ `);
          showPrompt = false;
        }

        if (data === "\x1b[A") {
          if (history.length === 0) return;
          if (historyIndex === -1) {
            savedLine = lineBuf;
            historyIndex = history.length - 1;
          } else if (historyIndex > 0) {
            historyIndex--;
          }
          term.write("\b \b".repeat(lineBuf.length));
          lineBuf = history[historyIndex];
          term.write(lineBuf);
          return;
        }

        if (data === "\x1b[B") {
          if (historyIndex === -1) return;
          if (historyIndex < history.length - 1) {
            historyIndex++;
            term.write("\b \b".repeat(lineBuf.length));
            lineBuf = history[historyIndex];
            term.write(lineBuf);
          } else {
            historyIndex = -1;
            term.write("\b \b".repeat(lineBuf.length));
            lineBuf = savedLine;
            term.write(lineBuf);
          }
          return;
        }

        if (data === "\r") {
          term.write("\r\n");
          const cmd = lineBuf.trim();
          lineBuf = "";
          if (cmd) executeCmd(cmd);
          else { term.write(`\x1b[32m${cwd || "~"}\x1b[0m $ `); showPrompt = false; }
          return;
        }
        if (data === "\x7f" || data === "\b") {
          if (lineBuf.length > 0) {
            lineBuf = lineBuf.slice(0, -1);
            term.write("\b \b");
          }
          return;
        }
        if (data === "\u0003") {
          term.write("^C\r\n");
          term.write(`\x1b[32m${cwd || "~"}\x1b[0m $ `);
          lineBuf = "";
          showPrompt = false;
          return;
        }
        if (data.length === 1 && data >= " ") {
          lineBuf += data;
          term.write(data);
        }
      });

      setShellAvailable(true);
      term.write(`\x1b[32m${cwd || "~"}\x1b[0m $ `);
      showPrompt = false;

      setTerminalReady(true);
    } catch (e) {
      if (!cancelled) {
        setTerminalError(e instanceof Error ? e.message : "Terminal initialization error");
        setTerminalReady(true);
      }
      }
    }
    initTerminal();
    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      if (xtermEl) xtermEl.removeEventListener("selectstart", onSelectStart);
    };
  }, []);

  const handleFallbackCmd = () => {
    const cmd = cmdInput.trim();
    if (!cmd) return;
    setFallbackOutput((prev) => prev + `$ ${cmd}\n`);
    setCmdInput("");
    import("@tauri-apps/plugin-shell")
      .then(({ Command }) => {
        const c = Command.create("zsh", ["-c", cmd]);
        c.stdout.on("data", (line: string) => setFallbackOutput((prev) => prev + line));
        c.stderr.on("data", (line: string) => setFallbackOutput((prev) => prev + line));
        c.execute().finally(() => setFallbackOutput((prev) => prev + "\n"));
      })
      .catch(() => setFallbackOutput((prev) => prev + "[error]\n\n"));
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="rounded-xl overflow-hidden bg-[#0e0e12] flex flex-col flex-1 min-h-0 relative mb-6">
        <style>{`
          .xterm {
            -webkit-user-select: none !important;
            user-select: none !important;
            -webkit-touch-callout: none !important;
          }
          .xterm .xterm-rows * {
            -webkit-user-select: none !important;
            user-select: none !important;
          }
          .xterm ::-moz-selection { background: transparent !important; }
          .xterm ::selection { background: transparent !important; }
          .xterm .xterm-helper-textarea {
            position: absolute !important;
            left: -99999px !important;
            top: -99999px !important;
            width: 0 !important;
            height: 0 !important;
            opacity: 0 !important;
            padding: 0 !important;
            border: none !important;
            outline: none !important;
            resize: none !important;
            pointer-events: none !important;
            z-index: -999 !important;
            overflow: hidden !important;
            display: block !important;
            clip: rect(0,0,0,0) !important;
          }
          .xterm-selection { display: none !important; }
        `}</style>
        <div ref={terminalRef} className="flex-1 min-h-0" />

        {terminalReady && !terminalError && shellAvailable !== false && (
          <div className="flex items-center justify-between px-3 py-1.5 bg-[#0a0a0f] border-t border-white/5 text-[10px] font-label-mono shrink-0">
            <span className="text-green-400/70 truncate max-w-[60%]">
              ⊡ {termStatus.cwd}
            </span>
            <div className="flex items-center gap-3 text-outline/40">
              {termStatus.exitCode !== null && (
                <span className={termStatus.exitCode === 0 ? "text-green-400/60" : "text-red-400/70"}>
                  exit {termStatus.exitCode}
                </span>
              )}
              <span>{termStatus.cmdCount} {t("code.terminal_cmds")}</span>
            </div>
          </div>
        )}

        {lastCmdOutput && (
          <button
            onClick={() => {
              const msg = `Tengo este output de terminal:\n\`\`\`\n$ ${lastCmdOutput.cmd}\n${lastCmdOutput.output}\`\`\`\n\n¿Puedes analizarlo?`;
              setPendingChatAction({ query: msg, autoSend: true });
              setTab("chat");
            }}
            className="absolute bottom-3 right-3 flex items-center gap-1.5 px-3 py-2 bg-surface-container/90 backdrop-blur-sm border border-outline-variant/20 rounded-lg text-[11px] font-medium text-on-surface-variant hover:text-on-surface hover:border-primary-container/40 transition-all shadow-lg z-10"
          >
            <span className="material-symbols-outlined text-[14px] text-primary-container/70">
              forum
            </span>
            {t("code.ask_agent")}
          </button>
        )}

        {copied && (
          <div className="absolute top-4 right-4 bg-primary-container/90 text-white px-3 py-1.5 rounded-lg text-[11px] font-medium shadow-lg animate-in fade-in slide-in-from-top-2 duration-200">
            {t("code.copied")}
          </div>
        )}
        {!terminalReady && !terminalError && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0e0e12] text-outline text-[13px]">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container status-dot-pulse" />
              {t("code.terminal_loading")}
            </span>
          </div>
        )}
        {terminalError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#0e0e12] p-6 text-center">
            <span className="material-symbols-outlined text-[40px] text-error/60">error_outline</span>
            <p className="text-[13px] text-on-surface-variant">{t("code.terminal_error_title")}</p>
            <p className="text-[11px] text-outline/60 font-mono bg-surface-container-low rounded-lg p-3 w-full max-w-md break-all">
              {terminalError}
            </p>
            <p className="text-[11px] text-outline/60">
              {t("code.terminal_error_hint")}
            </p>
          </div>
        )}
        {terminalReady && shellAvailable === false && !terminalError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 bg-[#0e0e12] p-6">
            <div className="text-center">
              <span className="material-symbols-outlined text-[48px] text-outline/20">terminal</span>
              <p className="text-[13px] text-on-surface-variant mt-3">
                {t("code.terminal_fallback_title")}
              </p>
              <p className="text-[11px] text-outline/60 mt-1">
                {t("code.terminal_fallback_hint")}
              </p>
            </div>
            <div className="w-full max-w-lg bg-surface-container-low border border-outline-variant/15 rounded-xl p-5">
              <div className="bg-[#0e0e12] rounded-lg p-4 max-h-48 overflow-y-auto custom-scrollbar mb-4 font-mono text-[13px] leading-relaxed">
                {fallbackOutput ? (
                  <pre className="text-on-surface whitespace-pre-wrap">{fallbackOutput}</pre>
                ) : (
                  <span className="text-on-surface-variant/30">
                    $ _<br />
                    &nbsp;&nbsp;{t("code.terminal_fallback_placeholder")}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  value={cmdInput}
                  onChange={(e) => setCmdInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleFallbackCmd()}
                  placeholder={t("code.terminal_fallback_placeholder")}
                  className="flex-1 bg-[#0e0e12] border border-outline-variant/20 rounded-lg px-4 py-3 text-[13px] font-mono text-on-surface placeholder-on-surface-variant/25 outline-none focus:border-primary-container/50 focus:shadow-[0_0_0_1px_rgba(37,99,235,0.2)] transition-all"
                  autoFocus
                />
                <button
                  onClick={handleFallbackCmd}
                  className="flex items-center gap-1.5 px-5 py-3 bg-primary-container text-white text-[13px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm"
                >
                  <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                  {t("code.run")}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
