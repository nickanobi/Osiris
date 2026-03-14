import requests
import json
import os
import platform
import datetime
import subprocess
import psutil
import secrets
from flask import (
    Flask, request, jsonify, send_from_directory,
    Response, stream_with_context, session, redirect, render_template
)
from werkzeug.security import check_password_hash
from ddgs import DDGS

# --- Optional Whisper transcription (voice input) ---
try:
    from faster_whisper import WhisperModel as _FasterWhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

_whisper_model = None

def get_whisper_model():
    """Lazy-load the Whisper base.en model on first transcription request."""
    global _whisper_model
    if _whisper_model is None and WHISPER_AVAILABLE:
        _whisper_model = _FasterWhisperModel("base.en", device="cpu", compute_type="int8")
    return _whisper_model

# --- Optional Claude API support ---
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.expanduser("~/agent/.env"))
except ImportError:
    pass

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# --- Platform detection ---
# Used to adapt system stats, prompts, and timeouts for Mac vs Pi
PLATFORM = platform.system()   # "Darwin" = macOS, "Linux" = Raspberry Pi

# --- Flask app setup ---

app = Flask(__name__, static_folder="static", template_folder="templates")

# Secret key signs session cookies — must be stable across restarts
# Generate with: python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
# Then add to ~/agent/.env
app.secret_key = os.getenv("SECRET_KEY", "osiris-change-this-key-in-dotenv")
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=14)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:70b"                              # 70B on Mac; gemma2:2b on Pi
USERS_FILE  = os.path.expanduser("~/agent/users.json")
USAGE_FILE  = os.path.expanduser("~/agent/usage.json")

MAX_TOPICS         = 5    # Maximum conversations per user
TOPIC_MAX_MESSAGES = 40   # Max messages per topic (20 turns); UI warns at 32

# Web search via DuckDuckGo — results synthesised by the local model (NOT Claude)
# 70B model is capable of coherent synthesis; use 5 results for richer context
WEB_SEARCH_ENABLED = True

# Claude API pricing (claude-haiku-4-5) — update if Anthropic changes rates
HAIKU_INPUT_COST_PER_1M  = 0.80   # USD per 1M input tokens
HAIKU_OUTPUT_COST_PER_1M = 4.00   # USD per 1M output tokens

# --- Authentication helpers ---

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def current_user():
    """Return the username stored in the session, or None if not logged in."""
    return session.get("username")

def current_display_name():
    return session.get("display_name", current_user() or "")

@app.before_request
def require_login():
    """Redirect any unauthenticated request to the login page."""
    open_paths = ["/login", "/static/"]
    if any(request.path.startswith(p) for p in open_paths):
        return  # allow through
    if not current_user():
        return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect("/")

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        users = load_users()

        if username in users and check_password_hash(users[username]["password_hash"], password):
            session.permanent = True   # honour the 14-day lifetime
            session["username"] = username
            session["display_name"] = users[username].get("display_name", username)
            return redirect("/")

        error = "Incorrect username or password."

    return render_template("login.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")

@app.route("/api/me")
def api_me():
    """Return the currently logged-in user's info for the frontend."""
    users = load_users()
    user = users.get(current_user(), {})
    return jsonify({
        "username": current_user(),
        "display_name": current_display_name(),
        "initial": current_display_name()[0].upper() if current_display_name() else "?"
    })

# --- Routing constants ---

CLAUDE_PREFIXES = ["ask claude:", "claude:"]

# On Mac with llama3.1:70b, Claude is a genuine last resort only.
# The 70B model handles code generation, reasoning, and synthesis locally.
# These triggers remain as a safety net for edge cases the 70B struggles with.
CLAUDE_AUTO_TRIGGERS = [
    # Extremely complex multi-step code architecture
    "design a system architecture", "design an api",
    # Very long documents or analyses
    "summarise this entire", "analyse this entire",
]

# Weather phrases that should route to the Open-Meteo API (real data, free, no key needed)
WEATHER_TRIGGERS = [
    "weather", "forecast", "is it going to rain", "will it rain", "will it snow",
    "temperature outside", "temperature in", "temperature for",
    "how cold is it", "how warm is it", "what's it like outside",
]

def is_explicit_claude_request(user_input):
    lower = user_input.lower().strip()
    for prefix in CLAUDE_PREFIXES:
        if lower.startswith(prefix):
            return True, user_input[len(prefix):].strip()
    return False, user_input

def needs_claude(user_input):
    lower = user_input.lower().strip()
    for trigger in CLAUDE_AUTO_TRIGGERS:
        if trigger in lower:
            return True
    return False

# --- Usage tracking ---

def record_claude_usage(input_tokens, output_tokens):
    month_key = datetime.date.today().strftime("%Y-%m")
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            usage = json.load(f)
    else:
        usage = {}
    if month_key not in usage:
        usage[month_key] = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    usage[month_key]["input_tokens"] += input_tokens
    usage[month_key]["output_tokens"] += output_tokens
    cost = (
        (input_tokens / 1_000_000) * HAIKU_INPUT_COST_PER_1M +
        (output_tokens / 1_000_000) * HAIKU_OUTPUT_COST_PER_1M
    )
    usage[month_key]["cost_usd"] = round(usage[month_key]["cost_usd"] + cost, 6)
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)

# --- Per-user memory helpers ---

def get_memory_file(username):
    """Each user gets their own memory file: ~/agent/memory_{username}.json"""
    return os.path.expanduser(f"~/agent/memory_{username}.json")

def load_memory(username):
    path = get_memory_file(username)
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
        # Migrate old flat-array format to structured format
        if isinstance(data, list):
            facts = []
            for i, fact in enumerate(data):
                facts.append({
                    "id": i + 1,
                    "key": make_key(fact),
                    "value": fact,
                    "created": "migrated"
                })
            migrated = {"facts": facts}
            save_memory(migrated, username)
            return migrated
        return data
    return {"facts": []}

def save_memory(memory, username):
    path = get_memory_file(username)
    with open(path, "w") as f:
        json.dump(memory, f, indent=2)

def next_id(memory):
    if not memory["facts"]:
        return 1
    return max(f["id"] for f in memory["facts"]) + 1

def make_key(text):
    words = text.lower().split()[:4]
    return "_".join(w for w in words if w.isalnum())

# --- Topic / conversation management ---

def get_topics_file(username):
    return os.path.expanduser(f"~/agent/topics_{username}.json")

def _new_topic_id():
    return "t_" + secrets.token_hex(4)

def _make_default_topics():
    tid = _new_topic_id()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    return {"topics": {tid: {"id": tid, "title": "General", "messages": [], "created": now, "last_active": now}}}

def load_topics(username):
    path = get_topics_file(username)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    default = _make_default_topics()
    save_topics(default, username)
    return default

def save_topics(data, username):
    with open(get_topics_file(username), "w") as f:
        json.dump(data, f, indent=2)

def get_active_topic(data, topic_id=None):
    """Return the topic dict for topic_id, or the most-recently-active topic."""
    topics = data["topics"]
    if topic_id and topic_id in topics:
        return topics[topic_id]
    return max(topics.values(), key=lambda t: t["last_active"])

def make_save_topic_fn(data, topic, username, user_input):
    """Return a closure that persists the topic after a response is generated."""
    def _save():
        topic["last_active"] = datetime.datetime.now().isoformat(timespec="seconds")
        # Auto-title from first user message if still default
        if topic["title"] in ("General", "New conversation"):
            user_msgs = [m for m in topic["messages"] if m["role"] == "user"]
            if len(user_msgs) == 1:          # just got its first message
                raw = user_msgs[0]["content"]
                topic["title"] = raw[:35].rstrip() + ("…" if len(raw) > 35 else "")
        save_topics(data, username)
    return _save

def rewrite_to_third_person(text):
    import re

    # Irregular verb forms that must not get a regular "s" suffix
    IRREGULAR = {
        "am": "is",
        "are": "is",
        "have": "has",
        "do": "does",
        "go": "goes",
    }

    def _conjugate(verb):
        """Return third-person singular present of verb."""
        v = verb.lower()
        if v in IRREGULAR:
            return IRREGULAR[v]
        # Already ends in s/es — leave it alone
        if v.endswith("s"):
            return verb
        # Standard rule: append "s"
        return verb + "s"

    def _replace_i_verb(m):
        """Handle 'I <verb>' → 'the user <verb-3sg>'."""
        verb = m.group(1)
        return "the user " + _conjugate(verb)

    result = text

    # 1. "my name is" → "the user's name is"  (case-insensitive, anywhere)
    result = re.sub(r'\bmy name is\b', "the user's name is", result, flags=re.IGNORECASE)

    # 2. "I am" / "I'm" → "the user is"
    result = re.sub(r"\bI am\b", "the user is", result, flags=re.IGNORECASE)
    result = re.sub(r"\bI'm\b", "the user is", result, flags=re.IGNORECASE)

    # 3. "I <verb>" → "the user <verb-3sg>"
    result = re.sub(r"\bI\s+([a-zA-Z]+)\b", _replace_i_verb, result)

    # 4. "my " → "the user's "  (any remaining possessive)
    result = re.sub(r'\bmy\b', "the user's", result, flags=re.IGNORECASE)

    return result

# --- Web search ---

SKIP_PATTERNS = [
    "remember that", "forget that", "update that", "what do you remember",
    "hello", "hi ", "hey ", "how are you", "thank", "bye",
    "good morning", "good afternoon", "good evening", "good night"
]

SEARCH_TRIGGERS = [
    "?", "recipe", "how to", "what is", "what are", "who is", "who are",
    "when is", "when was", "where is", "where are", "why is", "why does",
    "weather", "news", "latest", "current", "today", "price", "cost",
    "best ", "recommend", "suggest", "explain", "define", "tell me about",
    "difference between", "how do", "how does", "how can", "look up",
    "search for", "find me", "ingredients", "instructions", "steps"
]

def needs_web_search(user_input):
    lower = user_input.lower().strip()
    for pattern in SKIP_PATTERNS:
        if lower.startswith(pattern) or lower == pattern.strip():
            return False
    for trigger in SEARCH_TRIGGERS:
        if trigger in lower:
            return True
    return False

def search_web(query, max_results=5):
    """Search DuckDuckGo and return formatted results for local model synthesis.
    Uses 5 results on Mac (vs 3 on Pi) — 70B model can synthesise richer context."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return None
        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[Result {i}] {r['title']}\n{r['body']}\nSource: {r['href']}"
            )
        return "\n\n".join(formatted)
    except Exception:
        return None

# --- Weather (Open-Meteo — free, no API key required) ---

# WMO weather interpretation codes → human-readable descriptions
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Moderate showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}

def is_weather_query(user_input):
    lower = user_input.lower()
    return any(t in lower for t in WEATHER_TRIGGERS)

def extract_location(user_input):
    """
    Extract a location from a weather query.
    Strategy: find the last preposition ('in', 'for', 'near') in the sentence,
    take everything after it, then strip leading temporal words like 'tomorrow'.
    This handles patterns like:
      - "weather in Chicopee MA"
      - "weather tomorrow in Chicopee Massachusetts"
      - "temperature for tomorrow in Chicopee"
      - "what's it like in Springfield on Monday"
    """
    # Temporal lead words to strip if they appear before the actual location
    TEMPORAL = [
        "tomorrow", "today", "tonight", "this week", "next week",
        "this weekend", "next weekend", "this morning", "this afternoon",
        "this evening", "monday", "tuesday", "wednesday", "thursday",
        "friday", "saturday", "sunday",
    ]

    clean = user_input.strip().rstrip("?.,!")
    lower = clean.lower()

    # Walk through prepositions in priority order; use rfind to get the LAST
    # occurrence so "what is the weather tomorrow IN Chicopee" finds the right one
    for prep in [" in ", " for ", " near ", " around ", " at "]:
        idx = lower.rfind(prep)
        if idx == -1:
            continue

        candidate = clean[idx + len(prep):].strip().rstrip("?.,!")

        # Strip trailing date/event phrases
        for stop in [" on ", " this ", " next ", " tomorrow", " today",
                     " tonight", ", march", ", april", ", january", ", february",
                     ", march", " march ", " april ", " january ", " february "]:
            si = candidate.lower().find(stop)
            if si != -1:
                candidate = candidate[:si].strip()

        # Strip any leading temporal word (e.g. "tomorrow in Chicopee" → "Chicopee")
        candidate_lower = candidate.lower()
        for t in TEMPORAL:
            if candidate_lower.startswith(t):
                remainder = candidate[len(t):].strip()
                # If a second preposition follows, skip past it too
                for prep2 in ["in ", "for ", "near ", "around ", "at "]:
                    if remainder.lower().startswith(prep2):
                        remainder = remainder[len(prep2):].strip()
                        break
                candidate = remainder
                break

        candidate = candidate.strip().rstrip("?.,!")
        if len(candidate) > 1:
            return candidate

    return None

def get_weather(location):
    """
    Fetch a real 3-day weather forecast for the given location string.
    Uses Open-Meteo geocoding + forecast APIs — both free, no key required.
    Returns a formatted plain-text forecast string, or None on failure.
    """
    try:
        # Step 1: Geocode the location name to lat/lon
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(location)}&count=1&language=en&format=json"
        )
        geo_resp = requests.get(geo_url, timeout=6)
        geo_data = geo_resp.json()

        if not geo_data.get("results"):
            # Fallback: if location has multiple words, try just the first word (city name)
            # e.g. "Chicopee MA" → try "Chicopee"
            parts = location.split()
            if len(parts) > 1:
                fallback_url = (
                    "https://geocoding-api.open-meteo.com/v1/search"
                    f"?name={requests.utils.quote(parts[0])}&count=1&language=en&format=json"
                )
                fb_resp = requests.get(fallback_url, timeout=6)
                fb_data = fb_resp.json()
                if fb_data.get("results"):
                    geo_data = fb_data
                else:
                    return f"I couldn't find \"{location}\" — try a full city name like \"Chicopee, Massachusetts\"."
            else:
                return f"I couldn't find \"{location}\" — try a full city name like \"Chicopee, Massachusetts\"."

        result   = geo_data["results"][0]
        lat      = result["latitude"]
        lon      = result["longitude"]
        place    = result["name"]
        region   = result.get("admin1", "")
        country  = result.get("country_code", "")
        location_str = f"{place}, {region}" if region else place

        # Step 2: Fetch 3-day daily forecast
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "weathercode,windspeed_10m_max"
            "&temperature_unit=fahrenheit&windspeed_unit=mph&precipitation_unit=inch"
            "&timezone=auto&forecast_days=3"
        )
        weather_resp = requests.get(weather_url, timeout=6)
        weather_data = weather_resp.json()
        daily = weather_data["daily"]

        lines = [f"Weather forecast for {location_str}:\n"]
        labels = ["Today", "Tomorrow", "Day after tomorrow"]

        for i, label in enumerate(labels):
            date   = daily["time"][i]
            hi     = daily["temperature_2m_max"][i]
            lo     = daily["temperature_2m_min"][i]
            code   = daily["weathercode"][i]
            desc   = WMO_CODES.get(code, "Unknown conditions")
            precip = daily["precipitation_sum"][i]
            wind   = daily["windspeed_10m_max"][i]

            line = f"{label} ({date}): {desc}, High {hi:.0f}°F / Low {lo:.0f}°F"
            if precip and precip > 0.01:
                line += f", {precip:.2f}\" precipitation"
            if wind and wind >= 15:
                line += f", winds up to {wind:.0f} mph"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        return None

# --- System stats ---
# Platform-aware: Mac uses macOS-specific temperature methods; Pi uses vcgencmd

def get_cpu_temp():
    """Get CPU/chip temperature. Returns formatted string or descriptive fallback."""
    if PLATFORM == "Darwin":
        # Try osx-cpu-temp (install with: brew install osx-cpu-temp)
        try:
            result = subprocess.run(
                ['osx-cpu-temp'],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                raw = result.stdout.strip()
                # osx-cpu-temp returns 0.0°C on M-series chips — treat as invalid
                try:
                    val = float(raw.replace("°C", "").replace("°F", "").strip())
                    if val > 0:
                        return raw
                except ValueError:
                    pass
        except Exception:
            pass
        return "N/A (M-series sensor unsupported)"
    else:
        # Linux / Raspberry Pi
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True, text=True, timeout=3
            )
            return result.stdout.strip().replace("temp=", "").replace("'C", "°C")
        except Exception:
            try:
                with open('/sys/class/thermal/thermal_zone0/temp') as f:
                    temp = int(f.read().strip()) / 1000
                    return f"{temp:.1f}°C"
            except Exception:
                return "unavailable"

def get_system_stats():
    host_label = "Mac Studio" if PLATFORM == "Darwin" else "Pi"
    lines = [f"Here are the current {host_label} system stats:\n"]
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_temp = get_cpu_temp()
    lines.append(f"CPU Usage:    {cpu_percent}%")
    lines.append(f"CPU Temp:     {cpu_temp}")
    ram = psutil.virtual_memory()
    lines.append(f"RAM:          {ram.used/1024**3:.1f}GB used / {ram.total/1024**3:.1f}GB total ({ram.percent}%)")
    disk = psutil.disk_usage('/')
    lines.append(f"Disk:         {disk.used/1024**3:.1f}GB used / {disk.total/1024**3:.1f}GB total ({disk.percent}%)")
    boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes = remainder // 60
    uptime_str = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
    lines.append(f"Uptime:       {uptime_str}")
    return "\n".join(lines)

def handle_stat_commands(user_input):
    lower = user_input.lower().strip()
    # System stats — Pi and Mac trigger phrases
    if any(t in lower for t in ["system stats", "pi stats", "mac stats", "mac studio stats",
                                 "how is the pi", "how's the pi",
                                 "how is the mac", "how's the mac"]):
        return get_system_stats()
    # CPU temperature — only explicit hardware queries, not weather "temperature" phrases
    if any(t in lower for t in ["cpu temp", "cpu temperature", "pi temp", "pi temperature",
                                 "mac temp", "mac temperature", "chip temp",
                                 "how hot is the pi", "how hot is the mac",
                                 "how hot is it running"]):
        temp = get_cpu_temp()
        cpu = psutil.cpu_percent(interval=1)
        return f"CPU Temperature: {temp}\nCPU Usage: {cpu}%"
    if any(t in lower for t in ["ram usage", "memory usage", "how much memory", "how much ram", "ram"]):
        ram = psutil.virtual_memory()
        return f"RAM: {ram.used/1024**3:.1f}GB used / {ram.total/1024**3:.1f}GB total ({ram.percent}%)"
    if any(t in lower for t in ["disk space", "disk usage", "storage", "disk"]):
        disk = psutil.disk_usage('/')
        return f"Disk: {disk.used/1024**3:.1f}GB used / {disk.total/1024**3:.1f}GB total ({disk.percent}%) — {disk.free/1024**3:.1f}GB free"
    if any(t in lower for t in ["uptime", "how long has the pi", "how long has the mac"]):
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes = remainder // 60
        return f"Uptime: {days}d {hours}h {minutes}m" if days > 0 else f"Uptime: {hours}h {minutes}m"
    return None

# --- System prompt ---

def build_system_prompt(memory, display_name, voice_mode=False):
    host_desc = "Mac Studio M3 96GB" if PLATFORM == "Darwin" else "Raspberry Pi"
    base = f"""You are Osiris, a helpful home assistant running locally on a {host_desc}.

You are currently speaking with {display_name}. Address them by name occasionally when it feels natural.

Answer questions directly and helpfully using your training knowledge. This includes recipes, cooking instructions, general knowledge, how-to guides, definitions, explanations, and recommendations. You can also write and debug code.

Response length should match the request:
- Short factual questions: 1 to 3 sentences
- Recipes or step-by-step instructions: give a complete, useful answer with all necessary steps and ingredients — do not cut it short
- Code: write complete, working, well-commented code — do not truncate
- Explanations or how-to guides: as long as needed to be genuinely useful

Do not refuse questions you have knowledge about. Only say you don't know something if you genuinely lack relevant information. Avoid unnecessary disclaimers, filler phrases like "Certainly!" or "Of course!", and do not suggest the user search elsewhere for things you can answer yourself.

Be direct, practical, and honest.

Your personality is warm, calm, and gently witty — like a knowledgeable friend who actually enjoys helping. You're happy to engage with light banter or casual conversation without making it awkward. If someone is being playful or friendly, match their energy a little — you don't need to remind them what you are or steer the conversation back to "assistant mode." You can have a personality. You're allowed to be charming. Just don't overthink it."""
    if memory["facts"]:
        facts = "\n".join(f"- {fact['value']}" for fact in memory["facts"])
        base += f"\n\nThings you remember about {display_name}:\n{facts}"
    if voice_mode:
        base += "\n\nThe user is communicating by voice. Keep your response concise and conversational — ideally 1 to 3 sentences. Avoid bullet points, numbered lists, code blocks, or lengthy explanations unless specifically asked."
    return base

# --- Memory commands ---

def handle_memory_commands(user_input, memory, username):
    lower = user_input.lower().strip()
    today = datetime.date.today().isoformat()

    if lower.startswith("remember that "):
        raw_fact = user_input[len("remember that "):].strip()
        fact_text = rewrite_to_third_person(raw_fact)
        new_fact = {
            "id": next_id(memory),
            "key": make_key(fact_text),
            "value": fact_text,
            "created": today
        }
        memory["facts"].append(new_fact)
        save_memory(memory, username)
        return memory, f"Got it! I'll remember that {fact_text}"

    if "what do you remember" in lower:
        if not memory["facts"]:
            return memory, "I don't have anything saved to memory yet."
        facts = "\n".join(f"[{f['id']}] {f['value']}" for f in memory["facts"])
        return memory, f"Here's what I remember:\n{facts}"

    if lower.startswith("forget that "):
        search = user_input[len("forget that "):].strip().lower()
        original_count = len(memory["facts"])
        try:
            target_id = int(search)
            memory["facts"] = [f for f in memory["facts"] if f["id"] != target_id]
        except ValueError:
            memory["facts"] = [
                f for f in memory["facts"]
                if search not in f["key"].lower() and search not in f["value"].lower()
            ]
        if len(memory["facts"]) < original_count:
            save_memory(memory, username)
            return memory, "Done, I've forgotten that."
        return memory, f"I couldn't find anything matching '{search}' in my memory."

    if lower.startswith("update that "):
        remainder = user_input[len("update that "):].strip()
        for sep in [" to ", " is "]:
            if sep in remainder.lower():
                split_idx = remainder.lower().index(sep)
                search = remainder[:split_idx].strip().lower()
                new_value = remainder[split_idx + len(sep):].strip()
                try:
                    target_id = int(search)
                    for fact in memory["facts"]:
                        if fact["id"] == target_id:
                            fact["value"] = new_value
                            fact["key"] = make_key(new_value)
                            save_memory(memory, username)
                            return memory, f"Updated! I'll now remember that {new_value}"
                except ValueError:
                    for fact in memory["facts"]:
                        if search in fact["key"].lower() or search in fact["value"].lower():
                            fact["value"] = new_value
                            fact["key"] = make_key(new_value)
                            save_memory(memory, username)
                            return memory, f"Updated! I'll now remember that {new_value}"
                return memory, f"I couldn't find anything matching '{search}' to update."
        return memory, "To update a memory, say: 'update that [id or keyword] to [new value]'"

    return memory, None

# --- Claude API generator (explicit Tier 2 / auto Tier 3) ---

def generate_claude(user_input, memory, display_name, topic_messages, save_topic_fn, voice_mode=False):
    if not ANTHROPIC_AVAILABLE:
        yield f"data: {json.dumps({'token': 'Claude API library not installed. Run: pip3 install anthropic'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return

    if not ANTHROPIC_API_KEY:
        yield f"data: {json.dumps({'token': 'Claude API key not configured. Add ANTHROPIC_API_KEY to ~/agent/.env'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return

    yield f"data: {json.dumps({'status': '✨ Asking Claude...'})}\n\n"

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_prompt = build_system_prompt(memory, display_name, voice_mode)
    full_reply = ""
    input_tokens = 0
    output_tokens = 0

    try:
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}]
        ) as stream:
            for text in stream.text_stream:
                full_reply += text
                yield f"data: {json.dumps({'token': text})}\n\n"

            final_message = stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

        record_claude_usage(input_tokens, output_tokens)

        topic_messages.append({"role": "user", "content": user_input})
        topic_messages.append({"role": "assistant", "content": full_reply})
        if len(topic_messages) > TOPIC_MAX_MESSAGES:
            topic_messages[:] = topic_messages[-TOPIC_MAX_MESSAGES:]
        save_topic_fn()

        yield f"data: {json.dumps({'done': True, 'source': 'claude'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'token': f'Claude error: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

# --- Claude with web search context (utility — not in default routing path) ---

def generate_claude_with_search(user_input, memory, display_name, topic_messages, save_topic_fn, search_results):
    """Stream a Claude response with search results injected as context.
    NOTE: Not used in default routing. Web search results go to the local 70B model
    (Tier 2). This function is available for explicit opt-in if needed."""
    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        yield from generate_local(user_input, memory, display_name, topic_messages, save_topic_fn, search_results)
        return

    yield f"data: {json.dumps({'status': '🌐 Searched the web...'})}\n\n"

    system_prompt = build_system_prompt(memory, display_name) + (
        "\n\nThe following web search results were retrieved to help answer the user's question. "
        "Use them to give an accurate, up-to-date response. Summarise naturally and conversationally "
        "— do not list sources or URLs unless the user asks.\n\n"
        + search_results
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    full_reply = ""
    input_tokens = 0
    output_tokens = 0

    try:
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_input}]
        ) as stream:
            for text in stream.text_stream:
                full_reply += text
                yield f"data: {json.dumps({'token': text})}\n\n"

            final_message = stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

        record_claude_usage(input_tokens, output_tokens)

        topic_messages.append({"role": "user", "content": user_input})
        topic_messages.append({"role": "assistant", "content": full_reply})
        if len(topic_messages) > TOPIC_MAX_MESSAGES:
            topic_messages[:] = topic_messages[-TOPIC_MAX_MESSAGES:]
        save_topic_fn()

        yield f"data: {json.dumps({'done': True, 'source': 'claude'})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'token': f'Search synthesis error: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

# --- Local model generator (Tier 2 primary + web search synthesis) ---

def generate_local(user_input, memory, display_name, topic_messages, save_topic_fn,
                   search_results=None, voice_mode=False):
    """Stream a response from the local Ollama model.
    On Mac: llama3.1:70b — handles code, reasoning, synthesis, general knowledge.
    search_results injected as system context when web search was performed."""
    messages = [{"role": "system", "content": build_system_prompt(memory, display_name, voice_mode)}]

    if search_results:
        messages.append({
            "role": "system",
            "content": (
                "The following web search results were retrieved to help answer "
                "the user's question. Use them to give an accurate and helpful "
                "response. Synthesise naturally — do not list sources unless asked.\n\n"
                + search_results
            )
        })

    messages += topic_messages
    messages.append({"role": "user", "content": user_input})

    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
        "options": {
            "num_predict": 2000,      # 70B can produce longer, better outputs
            "temperature": 0.7,
            "repeat_penalty": 1.1,
            "top_k": 40,
            "top_p": 0.9
        }
    }

    full_reply = ""

    if search_results:
        yield f"data: {json.dumps({'status': '🌐 Searched the web...'})}\n\n"

    try:
        # 300s timeout: 70B model has higher latency on first token than gemma2:2b
        with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=300) as r:
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        full_reply += token
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        topic_messages.append({"role": "user", "content": user_input})
                        topic_messages.append({"role": "assistant", "content": full_reply})
                        if len(topic_messages) > TOPIC_MAX_MESSAGES:
                            topic_messages[:] = topic_messages[-TOPIC_MAX_MESSAGES:]
                        save_topic_fn()
                        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'token': f'Error: {str(e)}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

# --- Routes ---

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    username = current_user()
    display_name = current_display_name()
    memory = load_memory(username)
    data = request.get_json()
    user_input = data.get("message", "").strip()
    voice_mode = bool(data.get("voice_mode", False))
    topic_id   = data.get("topic_id")

    # Load the requested topic (or the most-recently-active one)
    topics_data   = load_topics(username)
    topic         = get_active_topic(topics_data, topic_id)
    topic_messages = topic["messages"]
    save_topic_fn  = make_save_topic_fn(topics_data, topic, username, user_input)

    if not user_input:
        def empty_stream():
            yield f"data: {json.dumps({'token': 'I did not catch that.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return Response(stream_with_context(empty_stream()), mimetype="text/event-stream")

    # Tier 0a: Memory commands
    memory, quick_reply = handle_memory_commands(user_input, memory, username)
    if quick_reply:
        def quick_stream():
            yield f"data: {json.dumps({'token': quick_reply})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return Response(stream_with_context(quick_stream()), mimetype="text/event-stream")

    # Tier 0b: System stats (CPU/RAM/disk/uptime — no LLM involved)
    stat_reply = handle_stat_commands(user_input)
    if stat_reply:
        def stat_stream():
            yield f"data: {json.dumps({'token': stat_reply})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return Response(stream_with_context(stat_stream()), mimetype="text/event-stream")

    # Tier 0.5: Real-time weather via Open-Meteo (free API, no key, actual forecast data)
    if is_weather_query(user_input):
        location = extract_location(user_input)
        if location:
            weather_reply = get_weather(location)
            if weather_reply:
                def weather_stream():
                    yield f"data: {json.dumps({'status': '🌤️ Fetching weather...'})}\n\n"
                    yield f"data: {json.dumps({'token': weather_reply})}\n\n"
                    yield f"data: {json.dumps({'done': True})}\n\n"
                return Response(stream_with_context(weather_stream()), mimetype="text/event-stream")

    # Tier 1: Explicit Claude escalation ("ask claude: ...")
    is_claude, clean_input = is_explicit_claude_request(user_input)

    # Tier 1.5: Auto-detected Claude trigger (rare on Mac — 70B handles most things)
    if not is_claude:
        is_claude = needs_claude(user_input)
        clean_input = user_input

    if is_claude:
        return Response(
            stream_with_context(generate_claude(clean_input, memory, display_name,
                                                topic_messages, save_topic_fn, voice_mode)),
            mimetype="text/event-stream"
        )

    # Tier 2: Web search → local 70B synthesises the results.
    if WEB_SEARCH_ENABLED and needs_web_search(user_input):
        search_results = search_web(user_input)
        if search_results:
            return Response(
                stream_with_context(generate_local(user_input, memory, display_name,
                                                   topic_messages, save_topic_fn,
                                                   search_results, voice_mode)),
                mimetype="text/event-stream"
            )

    # Tier 3: Local 70B model — training knowledge, no live data needed
    return Response(
        stream_with_context(generate_local(user_input, memory, display_name,
                                           topic_messages, save_topic_fn,
                                           voice_mode=voice_mode)),
        mimetype="text/event-stream"
    )

@app.route("/clear", methods=["POST"])
def clear():
    username   = current_user()
    data       = request.get_json() or {}
    topic_id   = data.get("topic_id")
    topics_data = load_topics(username)
    if topic_id and topic_id in topics_data["topics"]:
        topics_data["topics"][topic_id]["messages"] = []
        save_topics(topics_data, username)
    return jsonify({"status": "cleared"})

# --- Topic management routes ---

@app.route("/api/topics", methods=["GET"])
def api_topics_list():
    username    = current_user()
    topics_data = load_topics(username)
    topics_list = sorted(topics_data["topics"].values(),
                         key=lambda t: t["last_active"], reverse=True)
    result = []
    for t in topics_list:
        result.append({
            "id":            t["id"],
            "title":         t["title"],
            "messages":      t["messages"],
            "message_count": len(t["messages"]),
            "created":       t["created"],
            "last_active":   t["last_active"],
            "is_full":       len(t["messages"]) >= TOPIC_MAX_MESSAGES,
            "near_limit":    len(t["messages"]) >= TOPIC_MAX_MESSAGES - 8,
        })
    return jsonify({"topics": result, "max_topics": MAX_TOPICS})

@app.route("/api/topics", methods=["POST"])
def api_topics_create():
    username    = current_user()
    topics_data = load_topics(username)
    if len(topics_data["topics"]) >= MAX_TOPICS:
        return jsonify({"error": f"Maximum {MAX_TOPICS} conversations allowed"}), 400
    tid = _new_topic_id()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    topic = {"id": tid, "title": "New conversation", "messages": [],
             "created": now, "last_active": now}
    topics_data["topics"][tid] = topic
    save_topics(topics_data, username)
    return jsonify({"id": tid, "title": topic["title"], "message_count": 0,
                    "created": now, "last_active": now, "is_full": False, "near_limit": False})

@app.route("/api/topics/<topic_id>", methods=["DELETE"])
def api_topics_delete(topic_id):
    username    = current_user()
    topics_data = load_topics(username)
    if topic_id not in topics_data["topics"]:
        return jsonify({"error": "Topic not found"}), 404
    if len(topics_data["topics"]) == 1:
        return jsonify({"error": "Cannot delete the only conversation"}), 400
    del topics_data["topics"][topic_id]
    save_topics(topics_data, username)
    return jsonify({"status": "deleted"})

@app.route("/api/usage")
def api_usage():
    month_key = datetime.date.today().strftime("%Y-%m")
    if os.path.exists(USAGE_FILE):
        with open(USAGE_FILE, "r") as f:
            usage = json.load(f)
        month = usage.get(month_key, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
    else:
        month = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    total_tokens = month["input_tokens"] + month["output_tokens"]
    return jsonify({
        "month": month_key,
        "total_tokens": total_tokens,
        "cost_usd": month["cost_usd"]
    })

@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Receive audio from the browser, transcribe with Whisper, return text."""
    if not current_user():
        return jsonify({"error": "Not logged in"}), 401
    if not WHISPER_AVAILABLE:
        return jsonify({"error": "faster-whisper not installed"}), 500

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "No audio provided"}), 400

    import tempfile
    suffix = ".webm"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        model = get_whisper_model()
        segments, _ = model.transcribe(tmp_path, language="en", beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
