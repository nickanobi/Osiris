// ── Voice mode ───────────────────────────────────────────────────
let voiceMode    = false;
let isRecording  = false;
let mediaRecorder = null;
let audioChunks  = [];

function handleVoiceBtn() {
  if (!voiceMode) {
    enterVoiceMode();
  } else if (!isRecording) {
    startRecording();
  } else {
    stopRecording();
  }
}

function enterVoiceMode() {
  voiceMode = true;
  updateVoiceModeUI();
  startRecording();
}

function exitVoiceMode() {
  if (isRecording && mediaRecorder) {
    mediaRecorder.onstop = null;
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
  }
  window.speechSynthesis.cancel();
  voiceMode = false;
  updateVoiceModeUI();
}

function updateVoiceModeUI() {
  const btn        = document.getElementById("voice-btn");
  const bar        = document.getElementById("voice-mode-bar");
  const statusText = document.getElementById("voice-status-text");

  btn.classList.toggle("voice-on",  voiceMode && !isRecording);
  btn.classList.toggle("recording", isRecording);
  bar.classList.toggle("visible",   voiceMode);

  if (isRecording) {
    statusText.textContent = "🔴 Recording — tap mic to stop";
  } else if (voiceMode) {
    statusText.textContent = "🎤 Voice mode — tap mic to speak";
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks  = [];
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    mediaRecorder = new MediaRecorder(stream, { mimeType });
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      await transcribeAndSend();
    };
    mediaRecorder.start();
    isRecording = true;
    updateVoiceModeUI();
  } catch (err) {
    console.error("Mic access error:", err);
    voiceMode   = false;
    isRecording = false;
    updateVoiceModeUI();
    addMessage("Microphone access was denied. Please allow mic access in your browser settings.", "agent");
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    updateVoiceModeUI();
  }
}

async function transcribeAndSend() {
  if (audioChunks.length === 0) return;
  const blob = new Blob(audioChunks, { type: "audio/webm" });
  if (blob.size < 1500) {
    updateVoiceModeUI();
    return;
  }

  const formData = new FormData();
  formData.append("audio", blob, "recording.webm");

  addThinking();
  setThinkingStatus("🎤 Transcribing...");
  setInputEnabled(false);

  try {
    const res  = await fetch("/transcribe", { method: "POST", body: formData });
    const data = await res.json();
    removeThinking();

    if (data.text && data.text.trim()) {
      await submitMessage(data.text);
    } else {
      setInputEnabled(true);
      updateVoiceModeUI();
      addMessage("Couldn't make out what you said — tap the mic and try again.", "agent");
    }
  } catch (err) {
    removeThinking();
    setInputEnabled(true);
    updateVoiceModeUI();
    addMessage("Transcription failed. Check the server logs.", "agent");
  }
}

function speakResponse(text) {
  if (!voiceMode) return;
  const clean = text
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/\*(.*?)\*/g, "$1")
    .replace(/#{1,6}\s+/g, "")
    .replace(/```[\s\S]*?```/g, "code block.")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\n{2,}/g, ". ")
    .replace(/\n/g, " ")
    .trim();

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate  = 1.05;
  utterance.pitch = 1.0;
  const voices    = window.speechSynthesis.getVoices();
  const preferred = voices.find(v =>
    v.name.includes("Samantha") ||
    v.name.includes("Google US English") ||
    (v.lang === "en-US" && v.localService)
  );
  if (preferred) utterance.voice = preferred;
  window.speechSynthesis.speak(utterance);
}
