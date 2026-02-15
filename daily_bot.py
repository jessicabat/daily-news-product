import feedparser
import json
import os
import nltk
from datetime import datetime, timezone
from newspaper import Article
from groq import Groq

# --- Configuration ---

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- AUTO-FIX NLTK ---
# checks if the necessary data exists. 
# if not, downloads silently.
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("⏳ Downloading NLTK data...")
    nltk.download('punkt', quiet=True)
# ---------------------

TOPICS = {
    "Tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://hnrss.org/frontpage",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        "https://www.wired.com/feed/rss",
    ],
    "AI": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
         "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    ],
    "Finance": [
        "https://finance.yahoo.com/news/rssindex",
        "https://www.investing.com/rss/news.rss",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://moxie.foxbusiness.com/google-publisher/latest.xml",
    ],
    "World News": [
        "https://feeds.npr.org/1004/rss.xml",
        "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
        "https://www.theguardian.com/world/rss",
        "https://feeds.bbci.co.uk/news/rss.xml",
    ],
    "Business": [
        "https://feeds.washingtonpost.com/rss/business",
        "https://moxie.foxbusiness.com/google-publisher/latest.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    ],
    "Stock Market": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.investing.com/rss/news.rss",
         "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://decrypt.co/feed",
    ],
}


# --- Step 2: Fetching & Scraping ---

def fetch_news(rss_urls, max_articles=5):
    """Fetch articles from RSS feeds, mixing sources to reduce single-source bias."""
    # Step 1: Parse all feeds and collect candidate entries per source
    feed_entries = []  # list of (entry, feed_title) grouped by feed
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get("title", "Unknown Source")
            entries = [(entry, source_name) for entry in feed.entries]
            if entries:
                feed_entries.append(entries)
        except Exception as e:
            print(f"  ⚠️  Could not parse feed: {url} — {e}")
            continue

    if not feed_entries:
        return []

    # Step 2: Round-robin across feeds so no single source dominates
    selected = []
    seen_links = set()
    max_per_round = 1  # take 1 article from each feed per round
    while len(selected) < max_articles and feed_entries:
        exhausted = []
        for feed_idx, entries in enumerate(feed_entries):
            if len(selected) >= max_articles:
                break
            taken = 0
            while entries and taken < max_per_round:
                entry, source_name = entries.pop(0)
                link = getattr(entry, "link", None)
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                try:
                    art = Article(link)
                    art.download()
                    art.parse()
                    selected.append({
                        "title": entry.get("title", art.title or "No Title"),
                        "link": link,
                        "text": art.text[:2000] if art.text else "",
                        "published": entry.get("published", "Unknown"),
                        "source": source_name,
                    })
                    taken += 1
                except Exception as e:
                    print(f"  ⚠️  Could not scrape article: {link} — {e}")
                    continue
            if not entries:
                exhausted.append(feed_idx)
        # Remove fully-consumed feeds (iterate in reverse to keep indices stable)
        for idx in reversed(exhausted):
            feed_entries.pop(idx)

    return selected[:max_articles]


# --- Step 3: AI Summarization ---

def generate_summary(topic, articles):
    """Use Groq (Llama 3 8b) to generate an executive summary of the articles."""
    if not articles:
        return "No articles were available to summarize for this topic."

    # Assemble context from articles
    context_parts = []
    for i, art in enumerate(articles, 1):
        context_parts.append(
            f"**Article {i}: {art['title']}**\n"
            f"Source: {art['source']} | Published: {art['published']}\n"
            f"{art['text']}\n"
        )

    context = "\n---\n".join(context_parts)

    prompt = (
        f"You are an expert analyst. Below are the top news articles for the topic: **{topic}**.\n\n"
        f"{context}\n\n"
        f"Based on these articles, provide a response in the following Markdown format:\n\n"
        f"## Executive Summary\n"
        f"Provide a concise 3-5 sentence overview of the most important developments.\n\n"
        f"## Market & Business Implications\n"
        f"Provide 3-5 bullet points on facts from the articles that are relevant to businesses, investors, or professionals. "
        f"Each bullet MUST be directly traceable to a specific article above. Do NOT speculate on future outcomes or give advice.\n\n"
        f"## Beginner-Friendly Summary\n"
        f"Re-explain the executive summary in simple, everyday language that someone with no background in {topic} could easily understand. "
        f"Avoid jargon and use short sentences. Do NOT add any information that was not in the Executive Summary.\n\n"
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert news analyst who provides concise, factual daily briefings. "
                        "STRICT RULES — violating any of these is a critical failure:\n"
                        "1. ONLY state facts that are explicitly present in the provided articles. "
                        "Never predict, speculate, or extrapolate beyond what the text says.\n"
                        "2. NEVER give advisory language such as 'investors should', 'companies should be prepared', "
                        "or 'it is important to monitor'. Report what happened, not what to do about it.\n"
                        "3. NEVER contradict information stated in the source articles. "
                        "If two sources conflict, note the disagreement instead of picking a side.\n"
                        "4. If a claim cannot be directly supported by a quote or fact from the articles, do not include it."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"  ⚠️  Groq API error for topic '{topic}': {e}")
        return "Summary generation failed due to an API error."


# --- Step 4: Main Loop & Data Storage ---

def main():
    """Main entry point: iterate topics, fetch news, summarize, and save to JSON."""
    print("🗞️  Daily News Bot — Starting...")

    daily_data = {}

    for topic, rss_urls in TOPICS.items():
        print(f"\n📰 Processing topic: {topic}")

        # Fetch and scrape articles
        print(f"  🔍 Fetching articles from {len(rss_urls)} feed(s)...")
        articles = fetch_news(rss_urls, max_articles=5)
        print(f"  ✅ Retrieved {len(articles)} article(s).")

        # Generate AI summary
        print(f"  🤖 Generating AI summary...")
        summary = generate_summary(topic, articles)
        print(f"  ✅ Summary generated.")

        # Store structured data
        daily_data[topic] = {
            "summary": summary,
            "articles": [
                {
                    "title": art["title"],
                    "link": art["link"],
                    "published": art["published"],
                    "source": art["source"],
                    "text": art["text"],
                }
                for art in articles
            ],
        }

    # Add metadata with generation timestamp
    daily_data["_meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save to JSON for the frontend to read
    output_path = "daily_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Done! Data saved to '{output_path}'.")


if __name__ == "__main__":
    main()