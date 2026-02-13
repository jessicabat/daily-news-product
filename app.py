import streamlit as st
import json
import os
from groq import Groq

if "GROQ_API_KEY" not in st.secrets:
    st.error("🚨 Groq API Key is missing! Please add it to Streamlit Secrets.")
    st.stop()

# ─── 1. Page Configuration ───────────────────────────────────────────────────
st.set_page_config(
    page_title="MarketMind | Daily Digest",
    page_icon="📰",
    layout="wide",
)

# ─── 2. Load Data ────────────────────────────────────────────────────────────
DATA_FILE = "daily_data.json"


@st.cache_data(ttl=300)  # cache for 5 minutes so we don't re-read on every interaction
def load_data() -> dict:
    """Load the JSON file produced by the backend bot."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


data = load_data()

# ─── 3. Sidebar Navigation ───────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/news.png", width=64)
    st.title("MarketMind")
    st.caption("Your AI-powered daily news digest")

    st.divider()

    # Topic selector – keys come from the data file produced by the bot
    available_topics = list(data.keys()) if data else ["Tech", "Finance", "World"]
    selected_topic = st.radio("📂 Select Topic", available_topics)

    st.divider()

    # Dashboard metrics (cosmetic / placeholder for now)
    st.subheader("📊 Dashboard Metrics")
    col1, col2 = st.columns(2)
    col1.metric("Sources", "12", delta="3 new")
    col2.metric("Latency", "1.2 s", delta="-0.3 s")

    st.divider()
    st.info("💡 Tip: Use the **Chat with Data** box at the bottom to ask questions about today's news.")

# ─── 4. Main Display ─────────────────────────────────────────────────────────
st.header(f"📰 {selected_topic} — Daily Digest")

topic_data = data.get(selected_topic, {})

if not topic_data:
    st.warning(
        "No data available for this topic yet. Make sure `daily_bot.py` has run at least once "
        "and produced a `daily_data.json` file."
    )
    st.stop()

# --- Executive Summary ---
summary = topic_data.get("summary", "_No summary available._")
st.subheader("🧠 Executive Summary")
st.markdown(summary)

# --- Source Articles (transparency layer) ---
articles = topic_data.get("articles", [])

with st.expander(f"🔗 View Source Articles ({len(articles)})", expanded=False):
    if articles:
        for idx, article in enumerate(articles, start=1):
            title = article.get("title", "Untitled")
            url = article.get("url", "#")
            source = article.get("source", "Unknown source")
            snippet = article.get("text", article.get("description", ""))[:200]

            st.markdown(f"**{idx}. [{title}]({url})**  \n*{source}*")
            if snippet:
                st.caption(snippet + "…")
            st.divider()
    else:
        st.info("No source articles recorded.")

# ─── 5. Chat with Data (RAG) ─────────────────────────────────────────────────
st.divider()
st.subheader("💬 Chat with Today's News")

# Build context from the articles
context_text = "\n\n".join(
    f"Title: {a.get('title', '')}\nSource: {a.get('source', '')}\n"
    f"Content: {a.get('text', a.get('description', ''))}"
    for a in articles
)

# Initialise chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Ask something about today's news…"):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build the system + user messages for Groq
    system_prompt = (
        "You are MarketMind, an expert news analyst. "
        "Answer the user's question based ONLY on the following news context. "
        "If the answer is not in the context, say so honestly.\n\n"
        "--- NEWS CONTEXT ---\n"
        f"{context_text}\n"
        "--- END CONTEXT ---"
    )

    messages_for_llm = [
        {"role": "system", "content": system_prompt},
        # Include recent chat history for multi-turn conversation
        *[
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-10:]  # last 10 turns
        ],
    ]

    # Stream response from Groq
    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=st.secrets["GROQ_API_KEY"])
            stream = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages_for_llm,
                temperature=0.4,
                max_tokens=1024,
                stream=True,
            )

            response_text = st.write_stream(
                (chunk.choices[0].delta.content or "" for chunk in stream)
            )

        except Exception as e:
            response_text = f"⚠️ Could not reach the AI service: `{e}`"
            st.error(response_text)

    # Persist assistant reply
    st.session_state.messages.append({"role": "assistant", "content": response_text})