import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { useAuthFetch } from "../auth/authFetch";
import { sampleUrl } from "../auth/config";
import { useAccessibility } from "../state/accessibility";
import { Icon } from "./Icon";
import { SampleLabel } from "./SampleLabel";

type Phase = "idle" | "loading" | "playing";

interface ReadAloudButtonProps {
  /** The text to read. */
  text: string;
  /** Pre-recorded audio of the same text in `public/samples/`: the last resort. */
  sampleFile: string;
}

const browserSpeech = (): SpeechSynthesis | null =>
  typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis : null;

/** A British English voice when the browser has one. */
function pickVoice(synth: SpeechSynthesis): SpeechSynthesisVoice | undefined {
  const voices = synth.getVoices();
  return (
    voices.find((v) => v.lang === "en-GB" && v.localService) ??
    voices.find((v) => v.lang === "en-GB") ??
    voices.find((v) => v.lang.startsWith("en"))
  );
}

/**
 * Reads `text` aloud, at the speed chosen in the accessibility settings:
 * 1. signed in: the server's voice (`POST /v1/read-aloud`, Google Gemini) when it's set up;
 * 2. otherwise, or if that fails: the browser's built-in voice (stays on this device);
 * 3. if the browser has no voice: the pre-recorded sample, clearly labelled.
 */
export function ReadAloudButton({ text, sampleFile }: ReadAloudButtonProps) {
  const { isAuthenticated } = useAuth();
  const authFetch = useAuthFetch();
  const { settings } = useAccessibility();
  const [phase, setPhase] = useState<Phase>("idle");
  const [isSample, setIsSample] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const release = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    objectUrlRef.current = null;
    browserSpeech()?.cancel();
  };

  useEffect(() => release, []);

  const playAudio = async (src: string, sample: boolean) => {
    const audio = new Audio(src);
    audio.playbackRate = settings.speechRate;
    audioRef.current = audio;
    audio.onended = () => setPhase("idle");
    setIsSample(sample);
    try {
      await audio.play();
      setPhase("playing");
    } catch {
      setPhase("idle");
      setNotice("Your browser blocked audio playback.");
    }
  };

  /** Speaks with the browser's own voice; false if the browser can't. */
  const speakInBrowser = (): boolean => {
    const synth = browserSpeech();
    if (!synth) return false;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-GB";
    utterance.rate = settings.speechRate;
    const voice = pickVoice(synth);
    if (voice) utterance.voice = voice;
    utterance.onend = () => setPhase("idle");
    utterance.onerror = () => setPhase("idle");
    synth.cancel();
    synth.speak(utterance);
    setIsSample(false);
    setPhase("playing");
    return true;
  };

  const start = async () => {
    release();
    setNotice(null);
    setPhase("loading");

    if (isAuthenticated) {
      const result = await authFetch<Blob>(
        "/v1/read-aloud",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        },
        (res) => res.blob(),
      );
      if (result.status === "ok") {
        objectUrlRef.current = URL.createObjectURL(result.data);
        return playAudio(objectUrlRef.current, false);
      }
      // 501 just means the server has no voice set up: the browser's voice is the plan.
      const noServerVoice = result.status === "error" && result.httpStatus === 501;
      if (!noServerVoice) {
        setNotice(
          result.status === "signin"
            ? result.message
            : `The online voice isn’t available right now (${result.message}). Using your browser’s voice.`,
        );
      }
    }
    if (speakInBrowser()) return;
    setNotice("Your browser can’t read text aloud, so here is a sample recording.");
    return playAudio(sampleUrl(sampleFile), true);
  };

  const stop = () => {
    release();
    setPhase("idle");
  };

  return (
    <div className="read-aloud">
      <button
        type="button"
        className="read-aloud-button"
        onClick={phase === "playing" ? stop : start}
        disabled={phase === "loading"}
        aria-pressed={phase === "playing"}
      >
        <Icon name={phase === "playing" ? "x" : "spark"} size={16} />
        {phase === "loading" ? "Preparing audio…" : phase === "playing" ? "Stop" : "Read aloud"}
      </button>
      {isSample && phase === "playing" && <SampleLabel>Sample audio</SampleLabel>}
      {notice && <small role="status">{notice}</small>}
    </div>
  );
}
