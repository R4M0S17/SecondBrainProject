# Plan de Implementación: Botón de Micrófono con whisper.cpp

**Autor**: Investigación técnica basada en whisper.cpp v1.8+ (ggml-org/whisper.cpp)  
**Target**: Cerebro2 — Macbook Pro M1 8GB RAM, Tauri + FastAPI (puerto 7842)  
**Fecha**: 2026-06-27  
**Estado**: Fases 1–5 implementadas ✅ · Testing completo ✅

---

## 1. Resumen Ejecutivo

Este plan describe la implementación completa del botón de micrófono para Cerebro2. La arquitectura usa **whisper.cpp en modo servidor** (`whisper-server`) como proceso residente en puerto 8765. El backend Python actúa de proxy entre el frontend Tauri y el servidor whisper. El frontend captura audio con `MediaRecorder`, lo convierte a WAV 16 kHz mono en el navegador (sin ffmpeg), y lo envía al backend vía `POST /api/transcribe`.

### Modelo recomendado para español

| Modelo | Disco | RAM en uso | Idle RAM | Velocidad M1 |
|--------|-------|------------|----------|--------------|
| `ggml-tiny` (multilingual) | 75 MB | ~273 MB | ~273 MB | RTF ~0.02 (50× realtime) |
| `ggml-base` (multilingual) | 142 MB | ~388 MB | ~388 MB | RTF ~0.04 (25× realtime) |

**Decisión: usar `ggml-base` multilingual.**  
Con Qwen 2B corriendo (~1.5–2 GB RAM), la suma total es ~2.3–2.4 GB, muy por debajo del límite seguro de 6 GB en 8 GB de RAM. El modelo base ofrece ~3× más precisión que tiny para español con un costo de solo +115 MB RAM. En M1 con Metal, 5 segundos de audio → transcripción completada en <500 ms.

**Por qué NO `tiny.en`**: es inglés-only. El usuario habla español.  
**Por qué NO `small`**: 852 MB RAM en servidor residente es mucho cuando el LLM ya ocupa ~2 GB.

### Budget de RAM total estimado

```
Qwen 2B (LLM principal)      ~1.500 MB
whisper-server (base)        ~  388 MB  ← residente, siempre en memoria
Embedding (MiniLM 384d)      ~  120 MB
Python runtime + FastAPI     ~  180 MB
React/Tauri WebView          ~  200 MB
Sistema operativo + buffer   ~2.000 MB
────────────────────────────────────────
TOTAL estimado               ~4.388 MB  ← dentro de 8 GB con margen cómodo
```

---

## 2. Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────┐
│  Frontend Tauri (WebView)                                │
│                                                         │
│  MicButton.tsx                                          │
│    │                                                    │
│    ├── MediaRecorder API (graba WebM/Opus)              │
│    ├── Web Audio API → resample 16 kHz mono             │
│    ├── WAV encoder (escritura manual del header PCM)    │
│    └── POST /api/transcribe (Blob WAV)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP multipart/form-data
┌──────────────────────▼──────────────────────────────────┐
│  FastAPI Backend (puerto 7842)                          │
│                                                         │
│  POST /api/transcribe                                   │
│    ├── valida tipo MIME + tamaño                        │
│    ├── escribe WAV a archivo temporal                   │
│    ├── proxea a whisper-server:8765/inference           │
│    └── retorna { text, language, duration_ms }         │
│                                                         │
│  GET  /api/transcribe/health                           │
│  POST /api/transcribe/start   (inicia whisper-server)  │
│  POST /api/transcribe/stop    (termina whisper-server) │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP multipart/form-data (WAV)
┌──────────────────────▼──────────────────────────────────┐
│  whisper-server (proceso residente, puerto 8765)        │
│                                                         │
│  Binario: build/bin/whisper-server                      │
│  Modelo:  bin/whisper/ggml-base.bin                     │
│  Metal:   activado por defecto en Apple Silicon         │
│  VAD:     desactivado (push-to-talk desde frontend)     │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Fase 1: Setup de whisper.cpp

### 3.1 Clonar y compilar

```bash
# desde la raíz del proyecto
git clone https://github.com/ggml-org/whisper.cpp bin/whisper-src
cd bin/whisper-src

# build con Metal (activado por defecto en Apple Silicon)
# DGGML_METAL=ON es redundante en M1 pero explícito es mejor
# NO incluir DWHISPER_COREML en primera iteración: requiere
# un paso extra de conversión del modelo con Python y no es
# necesario — Metal ya da 50× realtime con ggml-base.
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_METAL=ON \
  -DWHISPER_BUILD_SERVER=ON

cmake --build build --config Release -j$(sysctl -n hw.logicalcpu)
```

Binarios producidos en `bin/whisper-src/build/bin/`:
- `whisper-server` — servidor HTTP residente
- `whisper-cli` — herramienta CLI para pruebas manuales

### 3.2 Descargar el modelo

```bash
cd bin/whisper-src
bash models/download-ggml-model.sh base

# mueve el modelo a una ubicación estable dentro del proyecto
mkdir -p ../../bin/whisper
cp models/ggml-base.bin ../../bin/whisper/ggml-base.bin
cd ../..
```

Estructura resultante:
```
bin/
  whisper/
    ggml-base.bin          (142 MB)
  whisper-src/
    build/bin/
      whisper-server       (binario compilado)
      whisper-cli
```

### 3.3 Verificar funcionamiento

```bash
# test de CLI: transcribir el sample incluido en el repo
bin/whisper-src/build/bin/whisper-cli \
  -m bin/whisper/ggml-base.bin \
  -f bin/whisper-src/samples/jfk.wav \
  -l en

# iniciar el servidor manualmente para verificar
bin/whisper-src/build/bin/whisper-server \
  -m bin/whisper/ggml-base.bin \
  --host 127.0.0.1 \
  --port 8765 \
  -l es \
  -t 4

# en otra terminal — test HTTP
curl 127.0.0.1:8765/inference \
  -H "Content-Type: multipart/form-data" \
  -F file="@bin/whisper-src/samples/jfk.wav" \
  -F temperature="0.0" \
  -F response_format="json"
# respuesta esperada: {"text":" And so my fellow Americans..."}
```

**Nota importante**: el servidor corre por defecto en puerto 8080. Cerebro2 usa 7842 y llama.cpp usa 8080. Siempre usar `--port 8765` para whisper-server.

### 3.4 .gitignore y .gitattributes

```gitignore
# añadir a .gitignore:
bin/whisper/
bin/whisper-src/
```

El modelo (142 MB) y el binario compilado no se versionan. Se documentan los comandos de setup en `Makefile`.

### 3.5 Makefile targets

```makefile
# añadir al Makefile existente:

whisper-build:
    git clone https://github.com/ggml-org/whisper.cpp bin/whisper-src
    cd bin/whisper-src && cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_METAL=ON -DWHISPER_BUILD_SERVER=ON
    cd bin/whisper-src && cmake --build build --config Release -j$$(sysctl -n hw.logicalcpu)

whisper-model:
    mkdir -p bin/whisper
    cd bin/whisper-src && bash models/download-ggml-model.sh base
    cp bin/whisper-src/models/ggml-base.bin bin/whisper/ggml-base.bin

whisper-server:
    bin/whisper-src/build/bin/whisper-server \
        -m bin/whisper/ggml-base.bin \
        --host 127.0.0.1 \
        --port 8765 \
        -l es \
        -t 4 \
        --convert
```

---

## 4. Fase 2: Backend Python — Gestión del Proceso y Endpoint

### 4.1 Módulo de gestión del proceso (`core/transcription/whisper_manager.py`)

Este módulo es el corazón del sistema. Gestiona el ciclo de vida del proceso `whisper-server`.

```python
"""
WhisperManager: gestión del proceso whisper-server residente.

Estrategia de RAM: el proceso arranca bajo demanda (primera llamada
a /api/transcribe) y se mantiene vivo hasta que se cierra la app.
No se hace lazy-shutdown para evitar la latencia de carga del modelo
(~2-3 segundos) en la siguiente solicitud.
"""

import asyncio
import logging
import os
import signal
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

WHISPER_SERVER_PORT = 8765
WHISPER_SERVER_URL = f"http://127.0.0.1:{WHISPER_SERVER_PORT}"
WHISPER_MODEL_PATH = Path("bin/whisper/ggml-base.bin")
WHISPER_BIN_PATH = Path("bin/whisper-src/build/bin/whisper-server")


class WhisperManager:
    """Gestiona el proceso whisper-server como proceso hijo residente."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._ready = False
        self._lock = asyncio.Lock()

    @property
    def is_available(self) -> bool:
        """True si el binario y el modelo existen en disco."""
        return WHISPER_BIN_PATH.exists() and WHISPER_MODEL_PATH.exists()

    @property
    def is_running(self) -> bool:
        if self._process is None:
            return False
        return self._process.poll() is None

    async def ensure_running(self) -> bool:
        """Arranca whisper-server si no está corriendo. Thread-safe."""
        async with self._lock:
            if self.is_running and self._ready:
                return True
            if not self.is_available:
                logger.warning("whisper-server no disponible: binario o modelo faltante")
                return False
            return await self._start()

    async def _start(self) -> bool:
        cmd = [
            str(WHISPER_BIN_PATH),
            "-m", str(WHISPER_MODEL_PATH),
            "--host", "127.0.0.1",
            "--port", str(WHISPER_SERVER_PORT),
            "-l", "auto",       # detección automática de idioma
            "-t", "4",          # 4 hilos (M1 tiene 8 cores, dejar margen para LLM)
            "--convert",        # habilitar conversión ffmpeg como fallback
        ]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # espera hasta que el servidor responda (máx 8 segundos)
        for _ in range(16):
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    resp = await client.get(f"{WHISPER_SERVER_URL}/")
                    if resp.status_code in (200, 404):
                        self._ready = True
                        logger.info("whisper-server listo en puerto %d", WHISPER_SERVER_PORT)
                        return True
            except httpx.ConnectError:
                continue

        logger.error("whisper-server no respondió en 8 segundos")
        self._process.kill()
        return False

    async def transcribe(self, wav_bytes: bytes, language: str = "auto") -> dict:
        """
        Envía audio WAV a whisper-server y retorna el texto transcrito.

        wav_bytes: audio WAV (16 kHz mono PCM), ya convertido por el frontend.
        language: "auto" para detección automática, "es", "en", etc.
        """
        if not await self.ensure_running():
            raise RuntimeError("whisper-server no disponible")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(tmp_path, "rb") as f:
                    response = await client.post(
                        f"{WHISPER_SERVER_URL}/inference",
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={
                            "temperature": "0.0",
                            "temperature_inc": "0.2",
                            "response_format": "verbose_json",
                            **({"language": language} if language != "auto" else {}),
                        },
                    )
                response.raise_for_status()
                return response.json()
        finally:
            os.unlink(tmp_path)

    async def health_check(self) -> dict:
        """Retorna el estado del proceso y su disponibilidad."""
        available = self.is_available
        running = self.is_running
        reachable = False

        if running:
            try:
                async with httpx.AsyncClient(timeout=1.0) as client:
                    await client.get(f"{WHISPER_SERVER_URL}/")
                reachable = True
            except Exception:
                pass

        return {
            "available": available,
            "running": running,
            "reachable": reachable,
            "model": str(WHISPER_MODEL_PATH) if available else None,
            "port": WHISPER_SERVER_PORT,
        }

    def shutdown(self):
        """Termina el proceso gracefully al cerrar la aplicación."""
        if self._process and self._process.poll() is None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            logger.info("whisper-server terminado")
```

### 4.2 Endpoints en `ui/tray/server.py`

Añadir al `AppState` y registrar en el router de FastAPI:

```python
# En AppState.__init__ o _build_app_state():
from core.transcription.whisper_manager import WhisperManager
app_state.whisper = WhisperManager()

# Registrar shutdown en el evento de cierre de la app:
@app.on_event("shutdown")
async def on_shutdown():
    app_state.whisper.shutdown()
```

```python
# Nuevos endpoints — añadir en server.py

@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("auto"),
):
    """
    Recibe audio WAV (16 kHz mono PCM) desde el frontend.
    Retorna el texto transcrito.

    El frontend es responsable de la conversión de formato.
    Este endpoint solo valida tamaño y tipo MIME.
    """
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB — 10 min de audio a 16 kHz

    if file.content_type not in ("audio/wav", "audio/wave", "audio/x-wav", "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Se requiere audio/wav")

    wav_bytes = await file.read()

    if len(wav_bytes) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio demasiado largo (máx 10 MB)")

    if len(wav_bytes) < 44:  # header WAV mínimo
        raise HTTPException(status_code=400, detail="Archivo WAV inválido")

    try:
        result = await app_state.whisper.transcribe(wav_bytes, language=language)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"whisper-server error: {e.response.status_code}")

    text = result.get("text", "").strip()
    detected_language = result.get("language", language)

    # verbose_json incluye segments con timestamps
    duration_ms = 0
    if "segments" in result and result["segments"]:
        last_seg = result["segments"][-1]
        duration_ms = int(last_seg.get("t1", 0) * 10)  # whisper usa centisegundos

    return {
        "text": text,
        "language": detected_language,
        "duration_ms": duration_ms,
    }


@app.get("/api/transcribe/health")
async def transcribe_health():
    return await app_state.whisper.health_check()


@app.post("/api/transcribe/start")
async def transcribe_start():
    """Pre-carga el modelo para evitar latencia en la primera transcripción."""
    success = await app_state.whisper.ensure_running()
    if not success:
        raise HTTPException(status_code=503, detail="No se pudo iniciar whisper-server")
    return {"status": "running"}


@app.post("/api/transcribe/stop")
async def transcribe_stop():
    app_state.whisper.shutdown()
    return {"status": "stopped"}
```

### 4.3 Actualizar `AppState` y tipos

```python
# En AppState (dataclass o clase existente):
whisper: "WhisperManager | None" = None
```

### 4.4 Ruta en `api/types.ts`

```typescript
export interface TranscribeResponse {
  text: string;
  language: string;
  duration_ms: number;
}

export interface TranscribeHealthResponse {
  available: boolean;
  running: boolean;
  reachable: boolean;
  model: string | null;
  port: number;
}
```

---

## 5. Fase 3: Frontend — Botón de Micrófono

### 5.1 La conversión de audio: el detalle más crítico

`MediaRecorder` en Tauri/WebView produce **WebM/Opus**, no WAV. whisper.cpp requiere **WAV PCM 16 kHz mono**. Hay que convertir en el frontend para no depender de ffmpeg en el backend.

La conversión usa la Web Audio API nativa del navegador:

```
MediaRecorder (WebM/Opus, sampleRate variable)
    ↓  Blob → ArrayBuffer
AudioContext.decodeAudioData()
    ↓  AudioBuffer (Float32, sampleRate del sistema, posiblemente stereo)
OfflineAudioContext (16000 Hz, mono)
    ↓  resample automático
AudioBuffer (Float32, 16000 Hz, 1 canal)
    ↓  Float32 → Int16 (PCM)
writeWavHeader() + Int16Array
    ↓
Blob("audio/wav")  → listo para enviar
```

### 5.2 Utilidad de conversión (`src/utils/audioConverter.ts`)

```typescript
/**
 * Convierte un Blob de audio (cualquier formato soportado por el navegador,
 * típicamente WebM/Opus desde MediaRecorder) a WAV PCM 16 kHz mono.
 *
 * No requiere librerías externas. Usa Web Audio API nativa.
 * Tamaño del resultado: ~32 KB por segundo de audio.
 */

const TARGET_SAMPLE_RATE = 16000;

function writeWavHeader(pcmData: Int16Array, sampleRate: number): ArrayBuffer {
  const numSamples = pcmData.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);          // PCM chunk size
  view.setUint16(20, 1, true);           // PCM format
  view.setUint16(22, 1, true);           // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate (16-bit mono)
  view.setUint16(32, 2, true);           // block align
  view.setUint16(34, 16, true);          // bits per sample
  writeString(36, "data");
  view.setUint32(40, numSamples * 2, true);

  const samples = new Int16Array(buffer, 44);
  for (let i = 0; i < numSamples; i++) {
    // clamp y convertir Float32 → Int16
    const s = Math.max(-1, Math.min(1, pcmData[i] as unknown as number));
    samples[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  return buffer;
}

export async function audioBlobToWav(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();

  // decodificar cualquier formato de audio que soporte el navegador
  const audioCtx = new AudioContext();
  const decoded = await audioCtx.decodeAudioData(arrayBuffer);
  await audioCtx.close();

  // resample a 16 kHz mono usando OfflineAudioContext
  const numFrames = Math.ceil(decoded.duration * TARGET_SAMPLE_RATE);
  const offlineCtx = new OfflineAudioContext(1, numFrames, TARGET_SAMPLE_RATE);

  const source = offlineCtx.createBufferSource();
  source.buffer = decoded;

  // si el audio es stereo, mezclar a mono sumando los canales
  if (decoded.numberOfChannels > 1) {
    const merger = offlineCtx.createChannelMerger(1);
    source.connect(merger);
    merger.connect(offlineCtx.destination);
  } else {
    source.connect(offlineCtx.destination);
  }

  source.start(0);
  const resampled = await offlineCtx.startRendering();

  // extraer PCM Float32 del canal 0
  const float32 = resampled.getChannelData(0);

  // convertir Float32 → Int16 y añadir header WAV
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  const wavBuffer = writeWavHeader(int16, TARGET_SAMPLE_RATE);
  return new Blob([wavBuffer], { type: "audio/wav" });
}
```

### 5.3 Función de llamada a la API (`src/api/client.ts`)

```typescript
// Añadir a client.ts:

export async function transcribeAudio(
  audioBlob: Blob,
  language = "auto"
): Promise<{ text: string; language: string; duration_ms: number }> {
  const formData = new FormData();
  formData.append("file", audioBlob, "audio.wav");
  formData.append("language", language);

  const response = await fetch(`${API_BASE}/api/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail ?? "Error al transcribir");
  }

  return response.json();
}

export async function getTranscribeHealth(): Promise<{
  available: boolean;
  running: boolean;
  reachable: boolean;
}> {
  const response = await fetch(`${API_BASE}/api/transcribe/health`);
  return response.json();
}
```

### 5.4 Componente `MicButton.tsx` (`src/components/chat/MicButton.tsx`)

```typescript
import React, { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../../api/client";
import { audioBlobToWav } from "../../utils/audioConverter";

type MicState = "idle" | "requesting" | "recording" | "processing" | "error";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export function MicButton({ onTranscript, disabled }: Props) {
  const [state, setState] = useState<MicState>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const startRecording = useCallback(async () => {
    setErrorMsg(null);
    setState("requesting");

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 44100,   // grabamos en alta calidad, luego convertimos
          channelCount: 1,     // solicitar mono desde el origen
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch (err) {
      setState("error");
      setErrorMsg("Permiso de micrófono denegado");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    // elegir el mejor formato disponible
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    const recorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      // limpiar el stream inmediatamente para liberar el micrófono
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;

      setState("processing");

      try {
        const rawBlob = new Blob(chunksRef.current, { type: mimeType });

        if (rawBlob.size < 1000) {
          setState("idle");
          return; // grabación demasiado corta, ignorar
        }

        const wavBlob = await audioBlobToWav(rawBlob);
        const result = await transcribeAudio(wavBlob);

        if (result.text.trim()) {
          onTranscript(result.text.trim());
        }
        setState("idle");
      } catch (err) {
        setState("error");
        setErrorMsg(err instanceof Error ? err.message : "Error al transcribir");
        setTimeout(() => setState("idle"), 3000);
      }
    };

    recorder.start(100); // chunks cada 100ms para tener datos continuos
    setState("recording");
  }, [onTranscript]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  // limpiar al desmontar
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const isRecording = state === "recording";
  const isProcessing = state === "processing" || state === "requesting";

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        disabled={disabled || isProcessing}
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={isRecording ? stopRecording : undefined}
        onTouchStart={startRecording}
        onTouchEnd={stopRecording}
        className={[
          "p-2 rounded-full transition-all duration-150 focus:outline-none",
          "focus-visible:ring-2 focus-visible:ring-offset-1",
          isRecording
            ? "bg-red-500 text-white scale-110 shadow-lg shadow-red-500/40"
            : isProcessing
            ? "bg-yellow-500/20 text-yellow-500 cursor-wait"
            : "bg-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50",
          disabled ? "opacity-40 cursor-not-allowed" : "",
        ].join(" ")}
        title={
          isRecording
            ? "Suelta para transcribir"
            : isProcessing
            ? "Procesando..."
            : "Mantén presionado para hablar"
        }
        aria-label="Botón de micrófono"
      >
        {isProcessing ? (
          // spinner
          <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          // micrófono
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 10a7 7 0 0014 0" />
            <line x1="12" y1="19" x2="12" y2="22" />
            <line x1="9" y1="22" x2="15" y2="22" />
          </svg>
        )}

        {/* anillo de pulso mientras graba */}
        {isRecording && (
          <span className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-30" />
        )}
      </button>

      {errorMsg && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs text-red-400 bg-zinc-800 border border-red-800 rounded-lg whitespace-nowrap shadow-lg">
          {errorMsg}
        </div>
      )}
    </div>
  );
}
```

### 5.5 Integrar `MicButton` en el chat input

El botón se coloca al lado del campo de texto existente. Al recibir el transcript, se inyecta en el input y se envía automáticamente (o se deja que el usuario lo edite — elegir según preferencia):

```typescript
// En ChatInput.tsx o el componente equivalente — añadir:
import { MicButton } from "./MicButton";

// Dentro del componente, donde está el input de texto:
const handleTranscript = useCallback((text: string) => {
  // opción A: inyectar en el input para que el usuario pueda editar
  setInputValue((prev) => prev ? `${prev} ${text}` : text);

  // opción B: enviar directamente al agente (comentar/descomentar según preferencia)
  // sendMessage(text);
}, [setInputValue]);

// En el JSX, al lado del botón de envío:
<MicButton
  onTranscript={handleTranscript}
  disabled={isSending}
/>
```

---

## 6. Fase 4: Permisos de Micrófono en Tauri

### 6.1 `tauri.conf.json` / capabilities

En Tauri v2, los permisos se declaran en `src-tauri/capabilities/default.json`:

```json
{
  "permissions": [
    "core:default",
    "shell:allow-open",
    "shell:allow-execute",
    "shell:allow-spawn"
  ]
}
```

**El permiso de micrófono en Tauri v2 es gestionado por el WebView nativo de macOS (WKWebView).** No requiere un permiso Tauri explícito — la primera llamada a `getUserMedia()` dispara el diálogo de permisos de macOS automáticamente. Sin embargo, la app necesita tener el entitlement correcto en el bundle.

### 6.2 `src-tauri/Info.plist`

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Cerebro2 necesita acceso al micrófono para transcribir voz a texto localmente usando Whisper.</string>
```

### 6.3 `src-tauri/entitlements.plist`

```xml
<key>com.apple.security.device.audio-input</key>
<true/>
```

Si la app no está firmada (desarrollo con Tauri dev mode), estos entitlements no se aplican — el diálogo de permisos de macOS aparece de todas formas por el WebView.

### 6.4 Verificar permisos antes de grabar

En macOS, si el usuario negó el permiso anteriormente, `getUserMedia` lanzará `NotAllowedError`. El componente ya maneja esto mostrando un mensaje de error. Para una mejor UX, se puede detectar el estado del permiso:

```typescript
// Al iniciar la app — opcional, para mostrar el estado del micrófono
const checkMicPermission = async (): Promise<"granted" | "denied" | "unknown"> => {
  if (!navigator.permissions) return "unknown";
  try {
    const result = await navigator.permissions.query({ name: "microphone" as PermissionName });
    return result.state === "granted" ? "granted" : result.state === "denied" ? "denied" : "unknown";
  } catch {
    return "unknown";
  }
};
```

---

## 7. Fase 5: Estrategia de RAM y Ciclo de Vida

### 7.1 Cuándo iniciar whisper-server

**Recomendado: arranque lazy en la primera transcripción.**

El modelo base tarda ~2-3 segundos en cargar. Para evitar que el usuario espere, se ofrece un pre-calentamiento opcional:

```python
# En _build_app_state() de main.py — al final, DESPUÉS de inicializar todo:
# Pre-calentamiento opcional: solo si la disponibilidad está confirmada
if app_state.whisper.is_available:
    asyncio.create_task(app_state.whisper.ensure_running())
    # esto corre en background — no bloquea el inicio de la app
```

Si el LLM principal ya consume mucha RAM en el arranque, se puede desactivar el pre-calentamiento y dejarlo lazy.

### 7.2 Auto-shutdown por inactividad (opcional)

Si se quiere liberar los ~388 MB del modelo base cuando no se usa el micrófono por un período largo:

```python
import asyncio
import time

class WhisperManager:
    IDLE_SHUTDOWN_SECONDS = 300  # 5 minutos sin uso → apagar

    def __init__(self):
        # ... (campos existentes)
        self._last_use: float = 0
        self._watchdog_task: asyncio.Task | None = None

    async def transcribe(self, wav_bytes: bytes, language: str = "auto") -> dict:
        self._last_use = time.monotonic()
        # ... (resto del método)

    async def _watchdog(self):
        """Apaga el servidor tras IDLE_SHUTDOWN_SECONDS de inactividad."""
        while True:
            await asyncio.sleep(60)
            if self.is_running and self._last_use > 0:
                idle = time.monotonic() - self._last_use
                if idle > self.IDLE_SHUTDOWN_SECONDS:
                    logger.info("whisper-server inactivo por %.0fs — apagando", idle)
                    self.shutdown()
```

**Nota**: con 8 GB de RAM y la carga estimada, el auto-shutdown NO es necesario. Solo implementarlo si se observan problemas reales de memoria.

### 7.3 Monitoreo en health endpoint

El endpoint `GET /api/transcribe/health` ya existe. Conectarlo al sistema de monitoreo existente en `/api/status` para visibilidad en el dashboard:

```python
# En GET /api/status — añadir al dict de respuesta:
"whisper": await app_state.whisper.health_check() if app_state.whisper else None,
```

---

## 8. Manejo de Errores y Edge Cases

| Escenario | Comportamiento esperado |
|-----------|------------------------|
| Binario no compilado | `MicButton` deshabilitado, tooltip "Whisper no configurado" |
| Modelo no descargado | Igual que arriba — `health.available = false` |
| whisper-server se cae | `ensure_running()` intenta reiniciar; muestra error si falla |
| Audio silencioso (<1 KB) | Frontend descarta, no envía |
| Grabación muy larga (>10 MB) | Backend retorna 413, frontend muestra "Audio demasiado largo" |
| Permiso de micrófono denegado | Frontend captura `NotAllowedError`, muestra mensaje de acción |
| Puerto 8765 ocupado | `ensure_running()` falla, log de error, health retorna `reachable: false` |
| AudioContext suspendido | Activar con `audioCtx.resume()` antes de `decodeAudioData()` |

### Manejo del AudioContext suspendido (gotcha de Tauri)

En algunos contextos de WebView, el `AudioContext` arranca suspendido. Corregir en `audioConverter.ts`:

```typescript
export async function audioBlobToWav(blob: Blob): Promise<Blob> {
  const audioCtx = new AudioContext();
  if (audioCtx.state === "suspended") {
    await audioCtx.resume();
  }
  // ... resto del código
}
```

---

## 9. i18n — Strings para `locales/es.json` y `locales/en.json`

```json
// es.json — añadir bajo "transcription":
"transcription": {
  "holdToSpeak": "Mantén presionado para hablar",
  "release": "Suelta para transcribir",
  "processing": "Transcribiendo...",
  "micDenied": "Permiso de micrófono denegado. Ve a Preferencias del Sistema → Privacidad → Micrófono.",
  "notAvailable": "Whisper no está configurado. Ejecuta: make whisper-build && make whisper-model",
  "errorShort": "Error al transcribir",
  "tooShort": "Grabación muy corta, intenta de nuevo"
}
```

```json
// en.json — añadir bajo "transcription":
"transcription": {
  "holdToSpeak": "Hold to speak",
  "release": "Release to transcribe",
  "processing": "Transcribing...",
  "micDenied": "Microphone permission denied. Go to System Preferences → Privacy → Microphone.",
  "notAvailable": "Whisper is not configured. Run: make whisper-build && make whisper-model",
  "errorShort": "Transcription error",
  "tooShort": "Recording too short, try again"
}
```

---

## 10. Testing

### 10.1 Tests del backend (`tests/test_transcription.py`)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# test: endpoint retorna 415 si no recibe audio/wav
async def test_transcribe_rejects_non_wav(tmp_app_state):
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        resp = await client.post(
            "/api/transcribe",
            files={"file": ("audio.mp3", b"fake", "audio/mpeg")},
        )
    assert resp.status_code == 415

# test: endpoint retorna 503 si whisper no está disponible
async def test_transcribe_503_when_unavailable(tmp_app_state):
    tmp_app_state.whisper = MagicMock()
    tmp_app_state.whisper.transcribe = AsyncMock(side_effect=RuntimeError("no disponible"))
    # crear un WAV mínimo válido (44 bytes de header)
    wav_header = b"RIFF" + b"\x00" * 40
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        resp = await client.post(
            "/api/transcribe",
            files={"file": ("audio.wav", wav_header, "audio/wav")},
        )
    assert resp.status_code == 503

# test: WhisperManager.health_check con proceso no iniciado
async def test_whisper_health_not_running():
    from core.transcription.whisper_manager import WhisperManager
    manager = WhisperManager()
    health = await manager.health_check()
    assert health["running"] is False
    assert health["reachable"] is False
```

### 10.2 Test manual de integración

```bash
# 1. Iniciar backend
make run

# 2. Verificar health
curl http://localhost:7842/api/transcribe/health

# 3. Pre-calentar (carga el modelo)
curl -X POST http://localhost:7842/api/transcribe/start

# 4. Grabar audio de prueba con sox (si disponible)
sox -n -r 16000 -c 1 /tmp/test.wav trim 0.0 3.0 synth 3 sine 440

# 5. Transcribir
curl http://localhost:7842/api/transcribe \
  -F file=@/tmp/test.wav \
  -F language=es

# 6. En Tauri dev: abrir la app y probar el botón de micrófono
cd ui/tray && npm run dev
```

---

## 11. Hoja de Ruta de Implementación

Los pasos están ordenados por dependencia. Cada uno es independientemente verificable.

## Estado actual (2026-06-27)

```
Fase 1: Setup whisper.cpp ✅
    ✓ Clonado: bin/whisper-src (v1.8+, commit 0ae02cdb)
    ✓ Compilado: cmake -DGGML_METAL=ON -DWHISPER_BUILD_SERVER=ON
    ✓ Modelo: ggml-base.bin (141 MB) → bin/whisper/ggml-base.bin
    ✓ Verificado con whisper-cli → "And so my fellow Americans..."
    ✓ Servidor HTTP verificado en puerto 8765

Fase 2: Backend Python ✅
    ✓ core/transcription/__init__.py (package init)
    ✓ core/transcription/whisper_manager.py (WhisperManager)
    ✓ Gestión de proceso: ensure_running, shutdown
    ✓ Proxy HTTP a whisper-server:8765/inference
    ✓ health_check: disponible, corriendo, alcanzable
    ✓ Endpoints en /api/transcribe, /api/transcribe/health,
      /api/transcribe/start, /api/transcribe/stop
    ✓ WhisperManager conectado a AppState + shutdown graceful
    ✓ whisper info en GET /api/status
    ✓ Tipos TypeScript: TranscribeResponse, TranscribeHealthResponse
    ✓ API client: transcribeAudio(), getTranscribeHealth(),
      startTranscribe(), stopTranscribe()
    ✓ 10 tests unitarios pasando
    ✓ Makefile targets: whisper-build, whisper-model, whisper-server, whisper-cli

Fase 3: Frontend — Botón de Micrófono ✅
    ✓ audioConverter.ts — conversión WebM/Opus → WAV 16 kHz mono
      (Web Audio API, OfflineAudioContext, resample nativo)
    ✓ MicButton.tsx — componente completo con estados:
      idle / requesting / recording / processing / error
    ✓ Press-and-hold para grabar, soltar para transcribir
    ✓ Transcript se inyecta en el input de texto (editable antes de enviar)
    ✓ Spinner durante procesamiento, glow pulse durante grabación
    ✓ Manejo de errores: permiso denegado, whisper no disponible,
      grabación muy corta, error de transcripción
    ✓ Integrado en InputArea.tsx (reemplaza botón placeholder existente)
    ✓ whisperAvailable leído desde status?.whisper?.available

Fase 4: Permisos macOS ✅
    ✓ NSMicrophoneUsageDescription en Info.plist
    ✓ com.apple.security.device.audio-input en entitlements.plist
    ✓ macOS bundle config en tauri.conf.json (minimumSystemVersion,
      entitlements, infoPlist)
    ✓ En dev mode: el WebView de Tauri maneja el diálogo de permisos
      nativo de macOS automáticamente al llamar getUserMedia()

i18n ✅
    ✓ Strings de transcripción en es.json (7 entradas)
    ✓ Strings de transcripción en en.json (7 entradas)

Fase 5: Estrategia de RAM ✅
    ✓ Auto-shutdown por inactividad (idle watchdog)
      - 5 minutos sin uso → apaga whisper-server
      - Libera ~388 MB de RAM automáticamente
      - Watchdog se inicia al arrancar el servidor
      - Se cancela al hacer shutdown manual
    ✓ last_use actualizado en cada transcribe()
    ✓ idle_seconds e idle_shutdown_seconds en health endpoint
    ✓ Reconexión automática en la siguiente solicitud (ensure_running)
    ✓ Pre-calentamiento al iniciar la app (background task en _build_app_state)

Testing:
    ✓ Tests unitarios de WhisperManager (14 tests):
      - is_available, is_running, ensure_running
      - health_check (not_running, not_available, reachable, idle_fields)
      - shutdown (noop, cancels watchdog)
      - transcribe (success, updates last_use, raises when unavailable)
    ✓ Tests de integración de API con ASGITransport (9 tests):
      - GET /api/transcribe/health sin whisper, con mock whisper
      - POST /api/transcribe con mock whisper (texto, idioma, duración)
      - POST /api/transcribe rechaza WAV vacío (400)
      - POST /api/transcribe rechaza audio grande (413)
      - POST /api/transcribe/start (éxito y fallo)
      - POST /api/transcribe/stop (noop cuando no hay whisper)
```

---

## 12. Consideraciones para Distribución como App

Cuando Cerebro2 se distribuya como aplicación empaquetada con Tauri:

1. **Incluir whisper-server como sidecar de Tauri**: el binario va en `src-tauri/binaries/whisper-server-aarch64-apple-darwin` (nombre exacto requerido por Tauri). Se invoca con `Command.sidecar("whisper-server")` desde TypeScript, o se gestiona desde Python con el path relativo al bundle.

2. **Incluir el modelo en los recursos**: el archivo `ggml-base.bin` (142 MB) se incluye en `src-tauri/resources/`. Tauri lo copia al directorio de recursos de la app. Python lo encuentra con `tauri::resource_path()` o mediante una variable de entorno que el wrapper Tauri pasa al proceso Python.

3. **Firma y notarización**: en una app firmada, los entitlements de micrófono son obligatorios en el `.entitlements` del target de release.

4. **Primera ejecución**: mostrar un mensaje informativo explicando que se usará el micrófono localmente y que ningún audio sale del dispositivo.

---

## Resumen de Archivos a Crear/Modificar

| Archivo | Acción | Descripción |
|---------|--------|-------------|
| `core/transcription/__init__.py` | ✅ Creado | Package init |
| `core/transcription/whisper_manager.py` | ✅ Creado | Gestión proceso whisper-server |
| `ui/tray/server.py` | ✅ Modificado | Añadido 4 endpoints de transcripción + shutdown + status |
| `ui/tray/src/utils/audioConverter.ts` | ✅ Creado | Conversión WebM→WAV 16kHz |
| `ui/tray/src/api/client.ts` | ✅ Modificado | Añadido `transcribeAudio()`, `getTranscribeHealth()`, etc. |
| `ui/tray/src/api/types.ts` | ✅ Modificado | Añadido `TranscribeResponse`, `TranscribeHealthResponse` |
| `ui/tray/src/components/chat/MicButton.tsx` | ✅ Creado | Componente botón micrófono |
| `ui/tray/src/components/chat/InputArea.tsx` | ✅ Modificado | Integrado MicButton (reemplaza placeholder) |
| `ui/tray/src/locales/es.json` | ✅ Modificado | Strings de transcripción (7 entradas) |
| `ui/tray/src/locales/en.json` | ✅ Modificado | Strings de transcripción (7 entradas) |
| `ui/tray/src-tauri/Info.plist` | ✅ Creado | NSMicrophoneUsageDescription |
| `ui/tray/src-tauri/entitlements.plist` | ✅ Creado | audio-input entitlement |
| `ui/tray/src-tauri/tauri.conf.json` | ✅ Modificado | Añadido macOS bundle config (entitlements, infoPlist) |
| `Makefile` | ✅ Modificado | Targets whisper-build, whisper-model, whisper-server, whisper-cli |
| `.gitignore` | ✅ Modificado | Ignorar bin/whisper/ y bin/whisper-src/ |
| `tests/test_transcription.py` | ✅ Creado | Tests del backend (23 tests: 14 unit + 9 integración) |
