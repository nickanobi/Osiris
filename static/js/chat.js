const chatWindow = document.getElementById("chat-window");
const userInput  = document.getElementById("user-input");
const sendBtn    = document.getElementById("send-btn");

// ── Topic state ──────────────────────────────────────────────────
let currentTopicId    = null;
let currentTopicTitle = "Osiris";
let cachedTopics      = [];

// Auto-resize textarea
userInput.addEventListener("input", () => {
  userInput.style.height = "auto";
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
});

// Send on Enter, new line on Shift+Enter
userInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

// ── Core send / submit logic ─────────────────────────────────────
async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || sendBtn.disabled) return;
  window.speechSynthesis.cancel();
  userInput.value = "";
  userInput.style.height = "auto";
  await submitMessage(text);
  userInput.focus();
}

async function submitMessage(text) {
  addMessage(text, "user");
  setInputEnabled(false);
  addThinking();

  let agentBubble    = null;
  let isClaudeSource = false;
  let fullText       = "";

  try {
    const res = await fetch("/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        message:    text,
        voice_mode: voiceMode,
        topic_id:   currentTopicId
      })
    });

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer    = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.status) setThinkingStatus(payload.status);

        if (payload.token !== undefined) {
          if (!agentBubble) {
            removeThinking();
            agentBubble = addStreamingBubble();
          }
          agentBubble.textContent += payload.token;
          fullText += payload.token;
          chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        if (payload.done) {
          isClaudeSource = payload.source === "claude";
          if (agentBubble) finalizeStreamingBubble(agentBubble, isClaudeSource);
          if (isClaudeSource) loadUsage();
          if (voiceMode && fullText) speakResponse(fullText);
          // Refresh topic list: picks up auto-title + updated message count
          loadTopics();
        }
      }
    }
  } catch (err) {
    removeThinking();
    addMessage("Could not reach Osiris. Is the server running?", "agent");
  } finally {
    setInputEnabled(true);
    updateVoiceModeUI();
  }
}

// ── Clear current topic ──────────────────────────────────────────
async function clearChat() {
  window.speechSynthesis.cancel();
  await fetch("/clear", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ topic_id: currentTopicId })
  });
  showEmptyState();
  updateLimitBar(0, false, false);
  loadTopics(); // Refresh counts
}

// ── Init ─────────────────────────────────────────────────────────
loadUsage();
loadCurrentUser();
loadTopics();
