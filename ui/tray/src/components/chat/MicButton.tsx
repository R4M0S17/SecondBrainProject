import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { transcribeAudio } from "../../api/client";
import { audioBlobToWav } from "../../utils/audioConverter";

type MicState = "idle" | "requesting" | "recording" | "processing" | "error";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  whisperAvailable: boolean;
}

export default function MicButton({ onTranscript, disabled, whisperAvailable }: Props) {
  const { t } = useTranslation();
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
          sampleRate: 44100,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
    } catch {
      setState("error");
      setErrorMsg(t("transcription.mic_denied"));
      setTimeout(() => setState("idle"), 3000);
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    const recorder = new MediaRecorder(stream, { mimeType });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;

      setState("processing");

      try {
        const rawBlob = new Blob(chunksRef.current, { type: mimeType });

        if (rawBlob.size < 1000) {
          setState("idle");
          return;
        }

        const wavBlob = await audioBlobToWav(rawBlob);
        const result = await transcribeAudio(wavBlob);

        if (result.text.trim()) {
          onTranscript(result.text.trim());
        }
        setState("idle");
      } catch (err) {
        setState("error");
        setErrorMsg(err instanceof Error ? err.message : t("transcription.error_short"));
        setTimeout(() => setState("idle"), 3000);
      }
    };

    recorder.start(100);
    setState("recording");
  }, [onTranscript, t]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

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

  if (!whisperAvailable) {
    return (
      <button
        disabled
        className="p-2 opacity-30 cursor-not-allowed text-on-surface-variant"
        aria-label={t("transcription.not_available")}
        title={t("transcription.not_available")}
      >
        <span className="material-symbols-outlined text-[20px]">mic_off</span>
      </button>
    );
  }

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
        className={
          isRecording
            ? "p-2 rounded-full bg-red-500 text-white scale-110 shadow-lg shadow-red-500/40 transition-all duration-150"
            : isProcessing
              ? "p-2 rounded-full bg-yellow-500/20 text-yellow-500 cursor-wait transition-all duration-150"
              : "p-2 rounded-full text-on-surface-variant hover:text-primary transition-colors"
        }
        title={
          isRecording
            ? t("transcription.release")
            : isProcessing
              ? t("transcription.processing")
              : t("transcription.hold_to_speak")
        }
        aria-label="Voice input"
      >
        {isProcessing ? (
          <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        ) : (
          <span className="material-symbols-outlined text-[20px]">mic</span>
        )}
        {isRecording && (
          <span className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-30" />
        )}
      </button>

      {errorMsg && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs text-red-400 bg-zinc-800 border border-red-800 rounded-lg whitespace-nowrap shadow-lg z-50">
          {errorMsg}
        </div>
      )}
    </div>
  );
}
