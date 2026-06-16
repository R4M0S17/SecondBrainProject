import { useEffect, useRef, useState, useCallback } from "react";
import { useChatStore } from "../../stores/chat";
import { useTabStore } from "../../stores/tab";
import type { FitAddon } from "@xterm/addon-fit";
import type { ToolCallRecord } from "../../api/types";

type CodeTab = "terminal" | "output" | "scratch";

const TABS: { id: CodeTab; label: string; icon: string; desc: string }[] = [
  { id: "terminal", label: "Terminal", icon: "terminal", desc: "Shell del sistema en vivo" },
  { id: "output", label: "Output", icon: "output", desc: "Resultados de herramientas ejecutadas" },
  { id: "scratch", label: "Scratch", icon: "edit_note", desc: "Bloc de notas rápido para código" },
];

const FORMATTED_NAMES: Record<string, string> = {
  execute_python: "Python",
  run_script: "Shell Script",
  write_file: "Write File",
  read_file: "Read File",
  search_web: "Web Search",
  create_calendar_event: "Calendar Event",
  add_reminder: "Reminder",
  delete_reminder: "Delete Reminder",
  delete_file: "Delete File",
};

function toolDisplayName(name: string): string {
  return FORMATTED_NAMES[name] ?? name.replace(/_/g, " ");
}

export default function CodePanel() {
  const [activeTab, setActiveTab] = useState<CodeTab>("terminal");
  const [terminalReady, setTerminalReady] = useState(false);
  const [terminalError, setTerminalError] = useState<string | null>(null);
  const [shellAvailable, setShellAvailable] = useState<boolean | null>(null);
  const [fallbackOutput, setFallbackOutput] = useState("");
  const [cmdInput, setCmdInput] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const commandsBtnRef = useRef<HTMLButtonElement>(null);
  const [commandsPos, setCommandsPos] = useState({ top: 0, right: 0 });
  const scratch = useTabStore((s) => s.scratch);
  const setScratch = useTabStore((s) => s.setScratch);
  const terminalRef = useRef<HTMLDivElement>(null);
  const fitAddon = useRef<FitAddon | null>(null);

  const messages = useChatStore((s) => s.messages);

  const toolCalls: (ToolCallRecord & { msgIdx: number; tcIdx: number })[] = [];
  for (const msg of messages) {
    if (msg.metadata?.tools_called) {
      for (let tci = 0; tci < msg.metadata.tools_called.length; tci++) {
        const tc = msg.metadata.tools_called[tci];
        toolCalls.push({ ...tc, msgIdx: toolCalls.length, tcIdx: tci });
      }
    }
  }

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
      term.write("\x1b[2m─ Terminal lista — escribe comandos, Enter para ejecutar ─\x1b[0m\r\n\r\n");

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
        setTerminalError(e instanceof Error ? e.message : "Error al inicializar terminal");
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

  const handleFallbackCmd = useCallback(() => {
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
  }, [cmdInput]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden px-4 md:px-6 lg:px-8 pt-4 pb-6 w-full min-w-0">
      <div className="flex items-center justify-between border-b border-outline-variant/20 mb-5 pb-3">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-[22px] text-primary-container">code</span>
          <h2 className="text-[15px] font-semibold text-on-surface">Code</h2>
        </div>
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium rounded-md transition-all ${
                activeTab === tab.id
                  ? "bg-primary-container/10 text-primary-container shadow-sm"
                  : "text-on-surface-variant/60 hover:text-on-surface hover:bg-surface-container-low"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {TABS.map((tab) => (
        <div
          key={tab.id}
          className="flex-1 flex flex-col min-h-0"
          style={{ display: activeTab === tab.id ? "flex" : "none" }}
        >
          <p className="text-[11px] text-on-surface-variant/60 mb-4 flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[14px] text-primary-container/60">info</span>
            {tab.desc}
          </p>

          {tab.id === "terminal" && (
            <>
              <div className="rounded-xl border border-outline-variant/15 overflow-hidden bg-surface-container-lowest shadow-lg flex flex-col flex-1 min-h-0">
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
                      <span><code className="font-mono text-primary-container">ls</code> <span className="text-outline/60">listar</span></span>
                      <span><code className="font-mono text-primary-container">cd &lt;d&gt;</code> <span className="text-outline/60">navegar</span></span>
                      <span><code className="font-mono text-primary-container">pwd</code> <span className="text-outline/60">ruta actual</span></span>
                      <span><code className="font-mono text-primary-container">mkdir</code> <span className="text-outline/60">crear carpeta</span></span>
                      <span><code className="font-mono text-primary-container">touch</code> <span className="text-outline/60">crear archivo</span></span>
                      <span><code className="font-mono text-primary-container">cat</code> <span className="text-outline/60">ver archivo</span></span>
                      <span><code className="font-mono text-primary-container">cp</code> <span className="text-outline/60">copiar</span></span>
                      <span><code className="font-mono text-primary-container">mv</code> <span className="text-outline/60">mover/renombrar</span></span>
                      <span><code className="font-mono text-primary-container">rm</code> <span className="text-outline/60">eliminar</span></span>
                      <span><code className="font-mono text-primary-container">rm -r</code> <span className="text-outline/60">eliminar carpeta</span></span>
                      <span><code className="font-mono text-primary-container">chmod</code> <span className="text-outline/60">permisos</span></span>
                      <span><code className="font-mono text-primary-container">clear</code> <span className="text-outline/60">limpiar</span></span>
                      <span><code className="font-mono text-primary-container">man</code> <span className="text-outline/60">manual</span></span>
                      <span><code className="font-mono text-primary-container">grep</code> <span className="text-outline/60">buscar texto</span></span>
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
                    <p className="text-[13px] text-on-surface-variant">Error al cargar la terminal</p>
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
                        Mientras tanto, puedes ejecutar comandos individuales aquí:
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
                          placeholder="$  escribe un comando y presiona Enter…"
                          className="flex-1 bg-surface-container-lowest border border-outline-variant/20 rounded-lg px-4 py-3 text-[13px] font-mono text-on-surface placeholder-on-surface-variant/25 outline-none focus:border-primary-container/50 focus:shadow-[0_0_0_1px_rgba(37,99,235,0.2)] transition-all"
                          autoFocus
                        />
                        <button
                          onClick={handleFallbackCmd}
                          className="flex items-center gap-1.5 px-5 py-3 bg-primary-container text-white text-[13px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm"
                        >
                          <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                          Ejecutar
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {tab.id === "output" && (
            <div className="flex-1 overflow-y-auto custom-scrollbar pr-1">
              {toolCalls.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-3 text-outline">
                  <span className="material-symbols-outlined text-[40px] text-outline/30">output</span>
                  <p className="text-[13px]">Aún no hay herramientas ejecutadas</p>
                  <p className="text-[11px] text-outline/60 text-center max-w-sm">
                    Pídele al agente que ejecute scripts, busque archivos o realice tareas. Los resultados aparecerán aquí.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {toolCalls
                    .slice()
                    .reverse()
                    .map((tc) => (
                      <div
                        key={`${tc.msgIdx}-${tc.tcIdx}`}
                        className="bg-surface-container-low border border-outline-variant/10 rounded-xl p-4 hover:border-outline-variant/25 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-2.5">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-primary-container/10 text-primary-container font-mono">
                              {toolDisplayName(tc.name)}
                            </span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              tc.approved
                                ? "bg-[#1a2e1a] text-[#4ade80]"
                                : "bg-[#2a1e1e] text-[#f87171]"
                            }`}>
                              {tc.approved ? "Ejecutado" : "Denegado"}
                            </span>
                          </div>
                          <span className="text-[10px] text-outline/50 font-label-mono">
                            {tc.latency_ms}ms
                          </span>
                        </div>
                        {tc.args_summary && tc.args_summary !== "{}" && (
                          <div className="mb-2">
                            <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                              Argumentos
                            </div>
                            <pre className="text-[11px] text-on-surface-variant/80 font-mono whitespace-pre-wrap bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5">
                              {tc.args_summary}
                            </pre>
                          </div>
                        )}
                        <div>
                          <div className="text-[9px] text-outline/50 uppercase tracking-wider font-bold mb-1">
                            Resultado
                          </div>
                          <pre className="text-[12px] text-on-surface font-mono whitespace-pre-wrap max-h-40 overflow-y-auto bg-surface-container-lowest/50 rounded-lg p-2.5 border border-outline-variant/5 leading-relaxed">
                            {tc.result_summary || (
                              <span className="text-on-surface-variant/40 italic">Sin resultado</span>
                            )}
                          </pre>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}

          {tab.id === "scratch" && (
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-end gap-2 mb-3">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(scratch).catch(() => {});
                    }}
                    className="flex items-center gap-1.5 px-3.5 py-2 bg-primary-container text-white text-[11px] font-medium rounded-lg hover:bg-primary-container/90 active:scale-[0.97] transition-all shadow-sm"
                  >
                    <span className="material-symbols-outlined text-[15px]">content_copy</span>
                    Copiar
                  </button>
                  <button
                    onClick={() => {
                      setScratch("");
                    }}
                    className="flex items-center gap-1.5 px-3.5 py-2 text-[11px] font-medium rounded-lg border border-outline-variant/20 text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low active:scale-[0.97] transition-all"
                  >
                    <span className="material-symbols-outlined text-[15px]">delete</span>
                    Limpiar
                  </button>
                </div>
              <div className="flex-1 rounded-xl border border-outline-variant/15 bg-surface-container-low overflow-hidden flex flex-col min-h-0">
                <div className="flex items-center justify-between px-4 py-2 border-b border-outline-variant/10 bg-surface-container-lowest/30 shrink-0">
                  <span className="text-[10px] text-outline/50 font-label-mono">
                    {scratch.length > 0
                      ? `${scratch.split("\n").length} líneas · ${scratch.length} caracteres`
                      : "Bloc de notas vacío"}
                  </span>
                </div>
                <textarea
                  value={scratch}
                  onChange={(e) => setScratch(e.target.value)}
                  placeholder='// Pegar o escribir código aquí&#10;// Útil para preparar scripts antes de pedirle al agente que los ejecute&#10;// Ejemplo:&#10;def hello():&#10;    print("Hola, mundo!")&#10;&#10;hello()'
                  className="flex-1 bg-transparent p-4 text-[13px] font-mono text-on-surface resize-none outline-none leading-relaxed placeholder-on-surface-variant/20"
                  spellCheck={false}
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
