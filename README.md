# 🧠 Market Digest — Automated Economic Intelligence

> Most LLM summaries hallucinate. This one doesn't. An end-to-end AI news pipeline that scrapes 18 global sources, generates executive summaries at 98% claim accuracy through negative-constraint prompt engineering with Llama 3.3 70B, and delivers them in a streaming interface with per-topic RAG chat — fully automated, every morning, in under a minute.

**[🌐 Product Website](https://jessicabat.github.io/market-digest/)** · **[🚀 Live App](https://market-digest.streamlit.app/)**

---

## Table of Contents

- [Architecture](#architecture)
- [Data Pipeline](#data-pipeline)
- [Technical Decisions](#technical-decisions)
- [Project Structure](#project-structure)
- [Local Setup & Reproduction](#local-setup--reproduction)
- [Deployment](#deployment)
- [Performance Metrics](#performance-metrics)
- [Future Roadmap](#future-roadmap)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (Cron)                       │
│                   Runs daily at 9:00 AM ET                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      daily_bot.py                               │
│                                                                 │
│  1. feedparser — Pulls RSS entries from 18 sources              │
│  2. newspaper3k — Scrapes & parses full article text            │
│  3. Groq API (Llama 3.3 70B) — Generates executive summaries   │
│  4. Writes structured JSON with metadata + timestamp            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
                   daily_data.json
                  (committed to repo)
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        app.py (Streamlit)                       │
│                                                                 │
│  • Landing page with topic card grid                            │
│  • Word-by-word streaming summary animation                     │
│  • Source transparency layer (expandable article list)          │
│  • Per-topic RAG chat powered by Groq streaming API             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Pipeline

### 1. Ingestion (`feedparser` + `newspaper3k`)

The bot iterates over **7 topic categories**, each mapped to 3–5 RSS feeds:

| Topic | Sources |
|-------|---------|
| **Tech** | TechCrunch, The Verge, Hacker News, Ars Technica, Wired |
| **AI** | TechCrunch AI, The Verge AI, Wired AI |
| **Finance** | Yahoo Finance, Fox Business, Investing.com, MarketWatch, CNBC |
| **World News** | Reuters, The Guardian, NPR, BBC |
| **Business** | Washington Post, Fox Business, CNBC, BBC Business |
| **Stock Market** | Yahoo Finance, MarketWatch, Investing.com, CNBC |
| **Crypto** | CoinTelegraph, CoinDesk, Decrypt |

For each feed entry, `newspaper3k` downloads and parses the full article HTML into clean text (capped at 2,000 chars per article to stay within LLM context limits).

### 2. Summarization (`Groq` / Llama 3.3 70B)

Each topic's articles are assembled into a structured prompt requesting three outputs:

- **Executive Summary** — 3–5 sentence overview of key developments
- **Market & Business Implications** — Bullet-point takeaways for professionals
- **Beginner-Friendly Summary** — Jargon-free re-explanation for general audiences

The system prompt uses a **negative-constraint architecture** — instead of only telling the model what to do, it explicitly defines failure modes:

1. **No speculation** — only facts explicitly present in the source articles
2. **No advisory language** — eliminates the "Advisor" effect (e.g., "investors should monitor…")
3. **No invented trends** — eliminates the "Pundit" effect (e.g., fabricating market implications)
4. **No unsupported claims** — every bullet must be directly traceable to a specific article

This approach improved claim accuracy from 44% to 98% across a 41-claim benchmark test spanning Tech, Finance, General News, and World News datasets.

### 3. Storage & Delivery

The bot writes all topic data + a `_meta.generated_at` UTC timestamp to `daily_data.json`. A GitHub Actions workflow commits this file back to the repo, which Streamlit Cloud auto-deploys from.

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **LLM Provider** | Groq (LPU Inference) | Groq's Language Processing Unit delivers ~280 tokens/sec — enabling real-time streaming in the chat interface without noticeable latency. Free tier is sufficient for daily batch + interactive use. |
| **Model** | Llama 3.3 70B Versatile | Best open-weight model at this parameter scale for instruction-following and factual summarization. Outperforms smaller models on multi-article synthesis tasks. |
| **Summarization temp** | `0.2` | Low temperature paired with negative-constraint system prompt to maximize factual grounding. Reduced from 0.5 after benchmarking showed significant hallucination reduction. |
| **RAG chat temp** | `0.3` | Lower temperature for the chat interface to keep answers strictly grounded in the provided article context, minimizing confabulation on factual queries. |
| **Chat context window** | Last 6 turns | Keeps token usage lean while supporting multi-turn follow-ups. Prevents context overflow on long conversations. |
| **Article text cap** | 2,000 chars | Balances article fidelity with LLM context limits — enough to capture the lede and key facts without exceeding token budgets across 5 articles per topic. |
| **Data format** | Flat JSON file | Eliminates database dependencies. The file is committed to the repo, making Streamlit Cloud deployment zero-config. Acceptable trade-off for a daily-refresh cadence. |
| **Scheduling** | GitHub Actions cron | Free, reliable, and keeps the entire stack in one repo. No need for external schedulers or always-on servers. |
| **Frontend framework** | Streamlit | Rapid prototyping with native streaming support (`st.write_stream`), session state management, and free cloud hosting. Ideal for data-heavy single-page apps. |

---

## Project Structure

```
├── .github/
│   └── workflows/
│       └── daily_run.yml      # GitHub Actions cron job (daily at 13:00 UTC)
├── app.py                     # Streamlit frontend — landing page, digest view, RAG chat
├── daily_bot.py               # Backend pipeline — RSS ingestion, scraping, summarization
├── daily_data.json            # Auto-generated output (committed by CI)
├── requirements.txt           # Python dependencies
└── README.md
```

---

## Local Setup & Reproduction

### Prerequisites

- Python 3.9+
- A [Groq API key](https://console.groq.com/) (free tier works)

### 1. Clone & Install

```bash
git clone https://github.com/jessicabat/daily-news-product.git
cd daily-news-product
pip install -r requirements.txt
pip install streamlit
```

### 2. Run the Bot (Data Generation)

```bash
export GROQ_API_KEY="gsk_your_key_here"
python daily_bot.py
```

This scrapes all feeds, generates summaries, and writes `daily_data.json`. Takes ~49 seconds in CI (GitHub Actions).

### 3. Run the App (Frontend)

Create a `.streamlit/secrets.toml` file:

```toml
GROQ_API_KEY = "gsk_your_key_here"
```

Then launch:

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

---

## Deployment

### Streamlit Cloud (Frontend)

1. Push to GitHub
2. Connect the repo at [share.streamlit.io](https://share.streamlit.io)
3. Add `GROQ_API_KEY` in **Settings → Secrets**
4. Deploy — the app reads `daily_data.json` directly from the repo

### GitHub Actions (Daily Pipeline)

The workflow at `.github/workflows/daily_run.yml` runs automatically. To configure:

1. Go to **Settings → Secrets and variables → Actions**
2. Add `GROQ_API_KEY` as a repository secret
3. The bot runs daily at 8:00 AM ET (13:00 UTC) and can also be triggered manually via `workflow_dispatch`

---

## Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| **Sources scraped** | 18 unique sources, 28 feeds | Across 7 topic categories |
| **Articles per topic** | 5 | Configurable via `max_articles` param |
| **Summary generation** | ~0.8s TTFT per topic | Groq LPU inference at ~280 tok/s |
| **End-to-end pipeline** | ~1 min 20s | Full CI run via GitHub Actions (bot step: 49s) |
| **Data freshness** | Daily at 9 AM ET | Automated via GitHub Actions cron |
| **Chat streaming latency** | < 500ms TTFB | Groq streaming API, first token |
| **Claim accuracy** | 98% | LLM-as-a-judge evaluation — up from 44% before negative-constraint prompt |
| **LLM grounding** | RAG-constrained | Chat answers restricted to article context only |

---

## Future Roadmap

- [ ] **Deduplication** — Detect and merge overlapping articles across feeds within the same topic
- [ ] **Sentiment analysis** — Add per-article and per-topic sentiment scoring
- [ ] **Email digest** — Optional daily email delivery via SendGrid or Resend
- [ ] **Historical tracking** — Store daily snapshots for trend analysis over time
- [ ] **Evaluation harness** — Automated factuality scoring against source articles (ROUGE / BERTScore)
- [ ] **Multi-language support** — Ingest and summarize non-English sources
