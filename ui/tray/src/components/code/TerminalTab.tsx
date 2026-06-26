import { useEffect, useRef, useState } from "react";

export default function TerminalTab() {
  const [terminalReady, setTerminalReady] = useState(false);
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const [shellAvailable, setShellAvailable] = useState<boolean | null>(null);
  const [fallbackOutput, setFallbackOutput] = useState("");
  const [cmdInput, setCmdInput] = useState("");
  const [copied, setCopied] = useState(false);
  const [showCommands, setShowCommands] = useState(false);
  const commandsRef = useRef<HTMLDivElement>(null);
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
      try {
        const { Command } = await import("@tauri-apps/plugin-shell");
        const r = await Command.create("zsh", ["-c", "echo $HOME"]).execute();
        if (r.stdout) cwd = r.stdout.trim();
      } catch {}

      const executeCmd = async (cmd: string) => {
        try {
          const { Command } = await import("@tauri-apps/plugin-shell");
          const fullCmd = cwd ? `cd "${cwd}" && ${cmd}` : cmd;
          const result = await Command.create("zsh", ["-c", fullCmd]).execute();
          if (result.stdout) term.write(result.stdout.replace(/\n/g, "\r\n"));
          if (result.stderr) term.write(`\x1b[31m${result.stderr.replace(/\n/g, "\r\n")}\x1b[0m`);
          if (result.code !== 0 && result.code !== null) {
            term.write(`\r\n\x1b[33m[exit code: ${result.code}]\x1b[0m`);
          }
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
        }
        term.write(`\r\n\x1b[32m${cwd || "~"}\x1b[0m $ `);
        showPrompt = false;
        term.scrollToBottom();
      };

      term.onData((data) => {
        term.scrollToBottom();
        if (showPrompt) {
          term.write(`\x1b[32m${cwd || "~"}\x1b[0m $ `);
          showPrompt = false;
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

  useEffect(() => {
    if (!showCommands) return;
    const handler = (e: MouseEvent) => {
      if (commandsRef.current && !commandsRef.current.contains(e.target as Node)) {
        setShowCommands(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showCommands]);

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

        <div ref={commandsRef} className="absolute top-2 right-2 z-10">
          <button
            onClick={() => setShowCommands((v) => !v)}
            className="bg-surface-container/80 backdrop-blur-sm border border-outline-variant/20 rounded-lg px-2.5 py-1.5 text-[10px] font-medium text-outline hover:text-on-surface transition-colors flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-[12px]">menu</span>
            Cmds
          </button>
          {showCommands && (
            <div
              className="absolute top-full right-0 mt-1 bg-surface-container/95 backdrop-blur-sm border border-outline-variant/20 rounded-xl shadow-xl p-3 min-w-[220px] z-50"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-[11px]">
                <span><code className="font-mono text-primary-container">ls</code> <span className="text-outline/60">list files</span></span>
                <span><code className="font-mono text-primary-container">cd &lt;d&gt;</code> <span className="text-outline/60">navigate</span></span>
                <span><code className="font-mono text-primary-container">pwd</code> <span className="text-outline/60">current path</span></span>
                <span><code className="font-mono text-primary-container">mkdir</code> <span className="text-outline/60">create folder</span></span>
                <span><code className="font-mono text-primary-container">touch</code> <span className="text-outline/60">create file</span></span>
                <span><code className="font-mono text-primary-container">cat</code> <span className="text-outline/60">view file</span></span>
                <span><code className="font-mono text-primary-container">cp</code> <span className="text-outline/60">copy</span></span>
                <span><code className="font-mono text-primary-container">mv</code> <span className="text-outline/60">move/rename</span></span>
                <span><code className="font-mono text-primary-container">rm</code> <span className="text-outline/60">delete file</span></span>
                <span><code className="font-mono text-primary-container">rm -r</code> <span className="text-outline/60">delete folder</span></span>
                <span><code className="font-mono text-primary-container">chmod</code> <span className="text-outline/60">permissions</span></span>
                <span><code className="font-mono text-primary-container">clear</code> <span className="text-outline/60">clear screen</span></span>
                <span><code className="font-mono text-primary-container">man</code> <span className="text-outline/60">manual page</span></span>
                <span><code className="font-mono text-primary-container">grep</code> <span className="text-outline/60">search text</span></span>
                <span><code className="font-mono text-primary-container">find</code> <span className="text-outline/60">find files</span></span>
                <span><code className="font-mono text-primary-container">echo</code> <span className="text-outline/60">print text</span></span>
              </div>
            </div>
          )}
        </div>

        {copied && (
          <div className="absolute top-4 right-4 bg-primary-container/90 text-white px-3 py-1.5 rounded-lg text-[11px] font-medium shadow-lg animate-in fade-in slide-in-from-top-2 duration-200">
            Copied
          </div>
        )}
        {!terminalReady && !terminalError && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#0e0e12] text-outline text-[13px]">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container status-dot-pulse" />
              Loading terminal…
            </span>
          </div>
        )}
        {terminalError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#0e0e12] p-6 text-center">
            <span className="material-symbols-outlined text-[40px] text-error/60">error_outline</span>
            <p className="text-[13px] text-on-surface-variant">Terminal failed to load</p>
            <p className="text-[11px] text-outline/60 font-mono bg-surface-container-low rounded-lg p-3 w-full max-w-md break-all">
              {terminalError}
            </p>
            <p className="text-[11px] text-outline/60">
              Asegúrate de ejecutar en Tauri (<code className="font-mono text-primary-container">npm run tauri:dev</code>) y que los permisos estén configurados.
            </p>
          </div>
        )}
        {terminalReady && shellAvailable === false && !terminalError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 bg-[#0e0e12] p-6">
            <div className="text-center">
              <span className="material-symbols-outlined text-[48px] text-outline/20">terminal</span>
              <p className="text-[13px] text-on-surface-variant mt-3">
                Terminal interactivo disponible solo en Tauri
              </p>
              <p className="text-[11px] text-outline/60 mt-1">
                In the meantime, you can run individual commands here:
              </p>
            </div>
            <div className="w-full max-w-lg bg-surface-container-low border border-outline-variant/15 rounded-xl p-5">
              <div className="bg-[#0e0e12] rounded-lg p-4 max-h-48 overflow-y-auto custom-scrollbar mb-4 font-mono text-[13px] leading-relaxed">
                {fallbackOutput ? (
                  <pre className="text-on-surface whitespace-pre-wrap">{fallbackOutput}</pre>
                ) : (
                  <span className="text-on-surface-variant/30">
                    $ _<br />
                    &nbsp;&nbsp;Los resultados aparecerán aquí
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  value={cmdInput}
                  onChange={(e) => setCmdInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleFallbackCmd()}
                  placeholder="$  type a command and press Enter…"
                  className="flex-1 bg-[#0e0e12] border border-outline-variant/20 rounded-lg px-4 py-3 text-[13px] font-mono text-on-surface placeholder-on-surface-variant/25 outline-none focus:border-primary-container/50 focus:shadow-[0_0_0_1px_rgba(37,99,235,0.2)] transition-all"
                  autoFocus
                />
                <button
                  onClick={handleFallbackCmd}
                  className="flex items-center gap-1.5 px-5 py-3 bg-primary-container text-white text-[13px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm"
                >
                  <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                  Run
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
