// ── Claude usage display ─────────────────────────────────────────
async function loadUsage() {
  try {
    const res  = await fetch("/api/usage");
    const data = await res.json();
    const usageEl = document.getElementById("claude-usage");
    const labelEl = document.getElementById("usage-label");
    const costEl  = document.getElementById("usage-cost");
    if (data.total_tokens > 0) {
      const tokens = data.total_tokens.toLocaleString();
      const cost   = data.cost_usd < 0.01 ? "<$0.01" : "$" + data.cost_usd.toFixed(2);
      labelEl.textContent = `✨ ${tokens} tokens`;
      costEl.textContent  = `${cost} this month`;
      usageEl.style.display = "block";
    } else {
      usageEl.style.display = "none";
    }
  } catch (e) {}
}

async function loadCurrentUser() {
  try {
    const res = await fetch("/api/me");
    if (res.ok) {
      const data = await res.json();
      document.getElementById("user-display-name").textContent = `${data.display_name} · ● Online`;
      document.getElementById("user-avatar").textContent = data.initial;
    }
  } catch (e) {}
}

async function signOut() {
  await fetch("/logout", { method: "POST" });
  window.location.href = "/login";
}
