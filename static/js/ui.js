function getTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function removeEmptyState() {
  const el = document.getElementById("empty-state");
  if (el) el.remove();
}

function showEmptyState() {
  chatWindow.innerHTML = "";
  const empty = document.createElement("div");
  empty.classList.add("empty-state");
  empty.id = "empty-state";
  empty.innerHTML = '<div class="icon">🤖</div><p>Osiris is ready. Say something!</p>';
  chatWindow.appendChild(empty);
}

function addMessage(text, role) {
  removeEmptyState();
  const row    = document.createElement("div");
  row.classList.add("bubble-row", role);
  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = text;
  const time = document.createElement("div");
  time.classList.add("timestamp");
  time.textContent = getTime();
  row.appendChild(bubble);
  row.appendChild(time);
  chatWindow.appendChild(row);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble;
}

function addStreamingBubble() {
  removeEmptyState();
  const row    = document.createElement("div");
  row.classList.add("bubble-row", "agent");
  row.id = "streaming-row";
  const bubble = document.createElement("div");
  bubble.classList.add("bubble", "streaming");
  bubble.textContent = "";
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble;
}

function finalizeStreamingBubble(bubble, isClaudeSource) {
  bubble.classList.remove("streaming");
  if (isClaudeSource) bubble.classList.add("claude-response");
  const row = document.getElementById("streaming-row");
  if (row) {
    row.id = "";
    const time = document.createElement("div");
    time.classList.add("timestamp");
    time.textContent = getTime() + (isClaudeSource ? " · Claude" : "");
    row.appendChild(time);
  }
}

function addThinking() {
  const row = document.createElement("div");
  row.classList.add("bubble-row", "agent");
  row.id = "thinking-row";
  const indicator = document.createElement("div");
  indicator.classList.add("thinking-indicator");
  indicator.id = "thinking-indicator";
  indicator.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
  row.appendChild(indicator);
  chatWindow.appendChild(row);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setThinkingStatus(text) {
  const indicator = document.getElementById("thinking-indicator");
  if (indicator) {
    indicator.innerHTML = `<span style="font-size:0.85em;color:var(--subtext);padding:0 4px">${text}</span>`;
  }
}

function removeThinking() {
  const el = document.getElementById("thinking-row");
  if (el) el.remove();
}

function setInputEnabled(enabled) {
  userInput.disabled = !enabled;
  sendBtn.disabled   = !enabled;
}

// ── Limit bar ────────────────────────────────────────────────────
function updateLimitBar(msgCount, isNearLimit, isFull) {
  const bar = document.getElementById("limit-bar");
  if (isFull) {
    bar.textContent = `⚠ Conversation limit reached (${msgCount}/40) — start a new topic to continue.`;
    bar.className = "full";
  } else if (isNearLimit) {
    bar.textContent = `⚠ Nearing conversation limit (${msgCount}/40 messages).`;
    bar.className = "warn";
  } else {
    bar.textContent = "";
    bar.className = "";
  }
}
