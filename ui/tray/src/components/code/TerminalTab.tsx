import { useEffect, useRef, useState } from "react";

export default function TerminalTab() {
  const [terminalReady, setTerminalReady] = useState(false);
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const [shellAvailable, setShellAvailable] = useState<boolean | null>(null);
  const [fallbackOutput, setFallbackOutput] = useState("");
  const [cmdInput, setCmdInput] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const commandsBtnRef = useRef<HTMLButtonElement>(null);
  const [commandsPos, setCommandsPos] = useState({ top: 0, right: 0 });
  const terminalRef = useRef<HTMLDivElement>(null);
  const fitAddon = useRef<import("@xterm/addon-fit").FitAddon | null>(null);

  useEffect(() => {
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
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
          selectionBackground: "#2563eb40",
          selectionInactiveBackground: "#ffffff15",
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
        rows: 24,
        scrollback: 5000,
        smoothScrollDuration: 80,
      });

      term.loadAddon(fit);
      fitAddon.current = fit;

      term.open(terminalRef.current);
      requestAnimationFrame(() => fit.fit());

      resizeObserver = new ResizeObserver(() => {
        try { fit.fit(); } catch { /* ignore */ }
      });
      resizeObserver.observe(terminalRef.current);

      term.write("\x1b[1;34m█▀▀ ▄▄▄ ▀█▀ ▄▄▄ ▄▄▄ ▀█▀ ▄▄▄ █▀▄\x1b[0m\r\n");
      term.write("\x1b[1;34m█▄▄ ▀▀▄  █  █▀  █▀▄  █  █▀█ █▀▄\x1b[0m\r\n");
      term.write("\r\n");
      term.write("\x1b[2m─ Terminal ready — type commands, Enter to run ─\x1b[0m\r\n\r\n");

      let lineBuf = "";
      let showPrompt = true;
      let cwd = "";
      try {
        const { Command } = await import("@tauri-apps/plugin-shell");
        const r = await Command.create("zsh", ["-c", "echo $HOME"]).execute();
        if (r.stdout) cwd = r.stdout.trim();
      } catch {} // fallback: cwd vacío → CWD del proceso

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
          if (cmd.startsWith("cd ")) {
            const dir = cmd.slice(3).trim() || "~";
            try {
              const r = await Command.create("zsh", ["-c", `cd "${cwd}" && cd "${dir}" && pwd`]).execute();
              if (r.stdout) cwd = r.stdout.trim();
            } catch {}
          }
        } catch (e) {
          term.write(`\r\n\x1b[31m[error]\x1b[0m`);
        }
        term.write("\r\n$ ");
        showPrompt = false;
      };

      term.onData((data) => {
        if (showPrompt) {
          term.write("$ ");
          showPrompt = false;
        }
        if (data === "\r") {
          term.write("\r\n");
          const cmd = lineBuf.trim();
          lineBuf = "";
          if (cmd) executeCmd(cmd);
          else { term.write("$ "); showPrompt = false; }
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
          term.write("^C\r\n$ ");
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
      term.write("$ ");
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
    };
  }, []);

  useEffect(() => {
    if (!showCommands) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (commandsBtnRef.current?.contains(target)) return;
      const dropdown = document.getElementById("commands-dropdown");
      if (dropdown && !dropdown.contains(target)) {
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
      <p className="text-[11px] text-on-surface-variant/60 mb-4 flex items-center gap-1.5">
        <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
        Live system shell
      </p>
      <div className="rounded-xl border border-outline-variant/15 overflow-hidden bg-surface-container-lowest shadow-lg flex flex-col flex-1 min-h-0 relative">
        <div className="flex items-center px-3 py-2 bg-surface-container-low border-b border-outline-variant/10 shrink-0 gap-2">
          <span className="text-[10px] text-on-surface-variant/40 font-label-mono">zsh — Cerebro Terminal</span>
          <button
            ref={commandsBtnRef}
            onClick={() => {
              if (!showCommands && commandsBtnRef.current) {
                const rect = commandsBtnRef.current.getBoundingClientRect();
                setCommandsPos({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
              }
              setShowCommands(!showCommands);
            }}
            className="ml-auto text-[10px] text-outline/50 hover:text-on-surface-variant/70 cursor-pointer flex items-center gap-1 transition-colors bg-transparent border-none"
          >
            <span className={`material-symbols-outlined text-[12px] transition-transform ${showCommands ? "rotate-90" : ""}`}>chevron_right</span>
            Comandos
          </button>
          {showCommands && (
            <div
              id="commands-dropdown"
              className="fixed z-50 bg-surface-container-low border border-outline-variant/15 rounded-lg shadow-lg p-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[11px]"
              style={{ top: commandsPos.top, right: commandsPos.right }}
            >
              <span><code className="font-mono text-primary-container">ls</code> <span className="text-outline/60">list</span></span>
              <span><code className="font-mono text-primary-container">cd &lt;d&gt;</code> <span className="text-outline/60">navigate</span></span>
              <span><code className="font-mono text-primary-container">pwd</code> <span className="text-outline/60">current path</span></span>
              <span><code className="font-mono text-primary-container">mkdir</code> <span className="text-outline/60">create folder</span></span>
              <span><code className="font-mono text-primary-container">touch</code> <span className="text-outline/60">create file</span></span>
              <span><code className="font-mono text-primary-container">cat</code> <span className="text-outline/60">view file</span></span>
              <span><code className="font-mono text-primary-container">cp</code> <span className="text-outline/60">copy</span></span>
              <span><code className="font-mono text-primary-container">mv</code> <span className="text-outline/60">move/rename</span></span>
              <span><code className="font-mono text-primary-container">rm</code> <span className="text-outline/60">delete</span></span>
              <span><code className="font-mono text-primary-container">rm -r</code> <span className="text-outline/60">delete folder</span></span>
              <span><code className="font-mono text-primary-container">chmod</code> <span className="text-outline/60">permissions</span></span>
              <span><code className="font-mono text-primary-container">clear</code> <span className="text-outline/60">clear</span></span>
              <span><code className="font-mono text-primary-container">man</code> <span className="text-outline/60">manual</span></span>
              <span><code className="font-mono text-primary-container">grep</code> <span className="text-outline/60">search text</span></span>
            </div>
          )}
        </div>
        <div ref={terminalRef} className="flex-1 min-h-0" />
        {!terminalReady && !terminalError && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface-container-lowest text-outline text-[13px]">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container status-dot-pulse" />
              Loading terminal…
            </span>
          </div>
        )}
        {terminalError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-surface-container-lowest p-6 text-center">
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
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 bg-surface-container-lowest p-6">
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
              <div className="bg-surface-container-lowest rounded-lg p-4 max-h-48 overflow-y-auto custom-scrollbar mb-4 font-mono text-[13px] leading-relaxed">
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
                  className="flex-1 bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3 text-[13px] font-mono text-on-surface placeholder-on-surface-variant/25 outline-none focus:border-primary-container/50 focus:shadow-[0_0_0_1px_rgba(37,99,235,0.2)] transition-all"
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
