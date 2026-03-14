// ── Topics drawer ────────────────────────────────────────────────
function openTopicsDrawer() {
  loadTopics(); // Always refresh when opening
  document.getElementById("topics-drawer").classList.add("open");
  document.getElementById("topics-overlay").classList.add("visible");
}

function closeTopicsDrawer() {
  document.getElementById("topics-drawer").classList.remove("open");
  document.getElementById("topics-overlay").classList.remove("visible");
}

function renderTopicMessages(messages) {
  chatWindow.innerHTML = "";
  if (!messages || messages.length === 0) {
    showEmptyState();
    return;
  }
  messages.forEach(msg => {
    const role   = msg.role === "user" ? "user" : "agent";
    const row    = document.createElement("div");
    row.classList.add("bubble-row", role);
    const bubble = document.createElement("div");
    bubble.classList.add("bubble");
    if (role === "agent") bubble.classList.add("claude-response");
    bubble.textContent = msg.content;
    row.appendChild(bubble);
    chatWindow.appendChild(row);
  });
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function loadTopics() {
  try {
    const res  = await fetch("/api/topics");
    const data = await res.json();
    const topics = data.topics; // sorted by last_active desc
    cachedTopics = topics;

    // If no current topic, pick the most recently active
    if (!currentTopicId && topics.length > 0) {
      currentTopicId    = topics[0].id;
      currentTopicTitle = topics[0].title;
      document.getElementById("current-topic-name").textContent = topics[0].title;
    }

    renderTopics(topics, data.max_topics);

    // Update limit bar for current topic
    const cur = topics.find(t => t.id === currentTopicId);
    if (cur) {
      updateLimitBar(cur.message_count, cur.near_limit, cur.is_full);
      // Sync title in case auto-title kicked in
      if (cur.title !== currentTopicTitle) {
        currentTopicTitle = cur.title;
        document.getElementById("current-topic-name").textContent = cur.title;
      }
    }

    return topics;
  } catch (e) {
    console.error("loadTopics error:", e);
    return [];
  }
}

function renderTopics(topics, maxTopics) {
  const list      = document.getElementById("topics-list");
  const newBtn    = document.getElementById("new-topic-btn");
  const countLbl  = document.getElementById("topics-count-label");

  list.innerHTML  = "";
  countLbl.textContent = `${topics.length} of ${maxTopics} conversations`;
  newBtn.disabled = topics.length >= maxTopics;

  topics.forEach(topic => {
    const item = document.createElement("div");
    item.className = "topic-item" + (topic.id === currentTopicId ? " active" : "");

    // Left: name + meta
    const main = document.createElement("div");
    main.className = "topic-item-main";

    const name = document.createElement("div");
    name.className = "topic-item-name";
    name.textContent = topic.title;

    const meta = document.createElement("div");
    meta.textContent = `${topic.message_count} / 40 messages`;
    if (topic.is_full) {
      meta.className = "topic-item-meta at-limit";
    } else if (topic.near_limit) {
      meta.className = "topic-item-meta near-limit";
    } else {
      meta.className = "topic-item-meta";
    }

    main.appendChild(name);
    main.appendChild(meta);

    // Right: delete button
    const delBtn = document.createElement("button");
    delBtn.className  = "topic-delete-btn";
    delBtn.textContent = "🗑";
    delBtn.title = "Delete conversation";
    delBtn.onclick = e => { e.stopPropagation(); deleteTopic(topic.id); };

    item.appendChild(main);
    item.appendChild(delBtn);
    item.onclick = () => switchTopic(topic.id, topic.title);
    list.appendChild(item);
  });
}

async function switchTopic(id, title) {
  if (id === currentTopicId) { closeTopicsDrawer(); return; }
  currentTopicId    = id;
  currentTopicTitle = title;
  document.getElementById("current-topic-name").textContent = title;
  closeTopicsDrawer();

  // Find messages in cache; re-fetch if needed
  let topic = cachedTopics.find(t => t.id === id);
  if (!topic) {
    const topics = await loadTopics();
    topic = topics.find(t => t.id === id);
  }
  renderTopicMessages(topic ? topic.messages : []);

  // Update limit bar with live counts
  if (topic) {
    updateLimitBar(topic.message_count, topic.near_limit, topic.is_full);
  }
}

async function createTopic() {
  const res = await fetch("/api/topics", { method: "POST" });
  if (!res.ok) {
    const data = await res.json();
    // Show as inline message rather than alert
    addMessage(data.error || "Cannot create more conversations — delete one first.", "agent");
    closeTopicsDrawer();
    return;
  }
  const data = await res.json();
  currentTopicId    = data.id;
  currentTopicTitle = data.title;
  document.getElementById("current-topic-name").textContent = data.title;
  closeTopicsDrawer();
  showEmptyState();
  updateLimitBar(0, false, false);
  await loadTopics();
}

async function deleteTopic(id) {
  const wasActive = (id === currentTopicId);
  const res = await fetch(`/api/topics/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json();
    addMessage(data.error || "Cannot delete this conversation.", "agent");
    closeTopicsDrawer();
    return;
  }
  // Reload topics and switch if we deleted the active one
  const topics = await loadTopics();
  if (wasActive && topics.length > 0) {
    const next = topics[0];
    currentTopicId    = next.id;
    currentTopicTitle = next.title;
    document.getElementById("current-topic-name").textContent = next.title;
    showEmptyState();
    updateLimitBar(next.message_count, next.near_limit, next.is_full);
    renderTopics(topics, 5);
  }
}
