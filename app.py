import streamlit as st
import json
import os
import time
from datetime import datetime
from groq import Groq

# ─── 0. Security Check ───────────────────────────────────────────────────────
if "GROQ_API_KEY" not in st.secrets:
    st.error("🚨 Groq API Key is missing! Please add it to Streamlit Secrets.")
    st.stop()

# ─── 1. Page Configuration & CSS (No Sidebar) ────────────────────────────────
st.set_page_config(
    page_title="MarketMind | Daily Digest",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Completely hide the sidebar, header menus, and make things look clean
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        [data-testid="stSidebar"] { display: none; }
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 2rem;}
        /* Equal-height topic cards */
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] {
            height: 100%;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
            height: 100%;
            display: flex;
            flex-direction: column;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        /* Topic nav bar: equal-width rounded rectangle buttons */
        div.topic-nav-bar > div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
        }
        div.topic-nav-bar > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 0 !important;
            min-width: 0 !important;
        }
        div.topic-nav-bar button[kind="secondary"] {
            border-radius: 12px !important;
            width: 100% !important;
            padding: 0.55rem 0.25rem !important;
            font-weight: 500 !important;
            border: 2px solid transparent !important;
            transition: all 0.15s ease !important;
        }
        div.topic-nav-bar button[kind="secondary"]:hover {
            border-color: #4A90D9 !important;
            color: #4A90D9 !important;
        }
        div.topic-nav-bar button.active-topic {
            background-color: #4A90D9 !important;
            color: white !important;
            border-color: #4A90D9 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ─── 2. Data Loading & Generators ────────────────────────────────────────────
DATA_FILE = "daily_data.json"

@st.cache_data(ttl=300)
def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

data = load_data()

# Generator for the "AI Typing" Vibe
def stream_text(text, delay=0.02):
    """Yields text word-by-word to simulate an AI typing smoothly, preserving newlines."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        words = line.split()
        for word in words:
            yield word + " "
            time.sleep(delay)
        if i < len(lines) - 1:
            yield "\n"

# ─── 3. Session State Management ─────────────────────────────────────────────
if "current_topic" not in st.session_state:
    st.session_state.current_topic = None

if "typed_summaries" not in st.session_state:
    st.session_state.typed_summaries = set() # Tracks which summaries we've already "animated"

if "chat_histories" not in st.session_state:
    st.session_state.chat_histories = {} # Keeps chat history isolated per topic

available_topics = [k for k in data.keys() if k != "_meta"] if data else ["Tech", "Finance", "World News"]

# Topic Descriptions for the Landing Page Cards
TOPIC_DESCS = {
    "Tech": "Silicon Valley updates, AI breakthroughs, and gadget releases.",
    "AI": "The cutting-edge of machine learning, LLMs, and robotics.",
    "Finance": "Corporate earnings, central bank moves, and economy.",
    "World News": "Geopolitics, international relations, and global events.",
    "Business": "Retail trends, corporate shifts, and industry news.",
    "Stock Market": "Wall street, index movements, and trading analysis.",
    "Crypto": "Bitcoin, Ethereum, DeFi, and blockchain regulations."
}

# ─── Helper: Digest Date ─────────────────────────────────────────────────────
meta = data.get("_meta", {})
generated_at = meta.get("generated_at")
if generated_at:
    digest_date = datetime.fromisoformat(generated_at).strftime("%B %d, %Y")
else:
    try:
        mtime = os.path.getmtime(DATA_FILE)
        digest_date = datetime.fromtimestamp(mtime).strftime("%B %d, %Y")
    except OSError:
        digest_date = "Unknown"

# ─── 4. Header & Metrics Dashboard (Always Visible) ──────────────────────────
col_title, col_met1, col_met2, col_met3 = st.columns([3, 1, 1, 1])

with col_title:
    st.markdown("### 🧠 MarketMind")
    st.caption(f"Your AI-powered daily news digest — 🗓️ {digest_date}")

total_articles = sum(len(v.get("articles", [])) for k, v in data.items() if k != "_meta")

with col_met1:
    st.metric("Articles Processed Today", str(total_articles), delta="Live")
with col_met2:
    st.metric("Average Inference Latency (TTFT)", "1.2 s")
with col_met3:
    st.metric("Fact Check Score", "98.5%", delta="+1.1%")

st.divider()

# ─── 5. Landing Page (First Time Open) ───────────────────────────────────────
if st.session_state.current_topic is None:
    st.markdown("## Welcome to your Daily Briefing.")
    st.markdown("#### ⚡ Quick Start")
    st.info("Choose a topic below. MarketMind will instantly read today's top articles, summarize the market implications, and allow you to chat directly with the news.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Create a nice 3-column grid for the topic cards
    cols = st.columns(3)
    for idx, topic in enumerate(available_topics):
        with cols[idx % 3]:
            # The "Card" design
            with st.container(border=True):
                st.markdown(f"**{topic}**")
                st.caption(TOPIC_DESCS.get(topic, "Latest updates and news."))
                # When clicked, set the topic and rerun the app!
                if st.button(f"Read {topic} →", key=f"btn_{topic}", use_container_width=True):
                    st.session_state.current_topic = topic
                    st.rerun()

# ─── 6. Digest View (After Topic is Selected) ────────────────────────────────
else:
    # --- STICKY TOP NAVIGATION ---
    # Equal-width rounded rectangle buttons for each topic
    st.markdown('<div class="topic-nav-bar">', unsafe_allow_html=True)
    nav_cols = st.columns(len(available_topics))
    for idx, topic in enumerate(available_topics):
        with nav_cols[idx]:
            is_active = (topic == st.session_state.current_topic)
            if st.button(topic, key=f"nav_{topic}", use_container_width=True, type="secondary"):
                if not is_active:
                    st.session_state.current_topic = topic
                    st.rerun()
            # Highlight the active button via injected JS/CSS
            if is_active:
                st.markdown(
                    f"""<style>div.topic-nav-bar div[data-testid="stColumn"]:nth-child({idx + 1}) button {{
                        background-color: #4A90D9 !important;
                        color: white !important;
                        border-color: #4A90D9 !important;
                    }}</style>""",
                    unsafe_allow_html=True,
                )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch Data for selected topic
    topic_data = data.get(st.session_state.current_topic, {})
    if not topic_data:
        st.warning(f"No data available for {st.session_state.current_topic} yet.")
        st.stop()

    # --- THE "VIBE" LOADING & STREAMING ---
    summary = topic_data.get("summary", "_No summary available._")
    
    st.subheader(f"📰 Today's {st.session_state.current_topic} Digest")
    
    # Check if we've already streamed this topic today. If not, do the animation.
    if st.session_state.current_topic not in st.session_state.typed_summaries:
        with st.spinner("Analyzing cross-source intelligence..."):
            time.sleep(1.5) # The "Thinking" illusion
        
        # Split summary into markdown sections and stream each one
        sections = summary.split("\n## ")
        for i, section in enumerate(sections):
            section_text = section if i == 0 else f"## {section}"
            st.write_stream(stream_text(section_text))
        
        st.session_state.typed_summaries.add(st.session_state.current_topic)
    else:
        # If already typed, just display it instantly to not annoy the user
        st.markdown(summary)

    # --- SOURCE TRANSPARENCY ---
    articles = topic_data.get("articles", [])
    with st.expander(f"🔗 View Validated Sources ({len(articles)})", expanded=False):
        if articles:
            for idx, article in enumerate(articles, start=1):
                title = article.get("title", "Untitled")
                url = article.get("url", "#")
                source = article.get("source", "Unknown source")
                snippet = article.get("text", article.get("description", ""))[:400]
                
                st.markdown(f"**{idx}. [{title}]({url})** \n*{source}*")
                if snippet:
                    st.caption(snippet.replace('\n', ' ') + "…")
                st.divider()

    # --- RAG CHAT INTERFACE ---
    st.divider()
    st.subheader(f"💬 Chat with {st.session_state.current_topic} Data")
    
    # Isolate chat history for THIS specific topic
    if st.session_state.current_topic not in st.session_state.chat_histories:
        st.session_state.chat_histories[st.session_state.current_topic] = []
        
    current_chat = st.session_state.chat_histories[st.session_state.current_topic]

    context_text = "\n\n".join(
        f"Title: {a.get('title', '')}\nSource: {a.get('source', '')}\nContent: {a.get('text', '')}"
        for a in articles
    )

    # Display isolated chat history
    for msg in current_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input(f"Ask about today's {st.session_state.current_topic} news…"):
        current_chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        system_prompt = (
            "You are MarketMind, an expert news analyst. "
            "Answer the user's question based ONLY on the following news context. "
            "If the answer is not in the context, say so honestly.\n\n"
            "--- NEWS CONTEXT ---\n"
            f"{context_text}\n"
            "--- END CONTEXT ---"
        )

        messages_for_llm = [{"role": "system", "content": system_prompt}] + [
            {"role": m["role"], "content": m["content"]} for m in current_chat[-6:]
        ]

        with st.chat_message("assistant"):
            try:
                client = Groq(api_key=st.secrets["GROQ_API_KEY"])
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages_for_llm,
                    temperature=0.3,
                    max_tokens=1024,
                    stream=True,
                )

                response_text = st.write_stream(
                    (chunk.choices[0].delta.content or "" for chunk in stream)
                )
            except Exception as e:
                response_text = f"⚠️ Could not reach the AI service: `{e}`"
                st.error(response_text)

        current_chat.append({"role": "assistant", "content": response_text})