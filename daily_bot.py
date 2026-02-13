import feedparser
import json
import os
import nltk
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
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.wired.com/feed/rss",
    ],
    "AI": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "https://www.wired.com/feed/category/artificial-intelligence/latest/rss",
    ],
    "Finance": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://finance.yahoo.com/news/rssindex",
    ],
    "World News": [
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.npr.org/1004/rss.xml",
    ],
    "Business": [
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    ],
    "Stock Market": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://decrypt.co/feed",
    ],
}


# --- Step 2: Fetching & Scraping ---

def fetch_news(rss_urls, max_articles=5):
    """Fetch articles from RSS feeds and scrape their full content."""
    articles = []

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if len(articles) >= max_articles:
                    break
                try:
                    art = Article(entry.link)
                    art.download()
                    art.parse()

                    articles.append({
                        "title": entry.get("title", art.title or "No Title"),
                        "link": entry.link,
                        "text": art.text[:2000] if art.text else "",
                        "published": entry.get("published", "Unknown"),
                        "source": feed.feed.get("title", "Unknown Source"),
                    })
                except Exception as e:
                    print(f"  ⚠️  Could not scrape article: {entry.link} — {e}")
                    continue
        except Exception as e:
            print(f"  ⚠️  Could not parse feed: {url} — {e}")
            continue

        if len(articles) >= max_articles:
            break

    return articles[:max_articles]


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
        f"Provide 3-5 bullet points on key takeaways for businesses, investors, or professionals.\n"
        f"## Beginner-Friendly Summary\n"
        f"Re-explain the executive summary in simple, everyday language that someone with no background in {topic} could easily understand. Avoid jargon and use short sentences.\n\n"
    )

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert news analyst who provides concise, insightful daily briefings.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.5,
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

    # Save to JSON for the frontend to read
    output_path = "daily_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(daily_data, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Done! Data saved to '{output_path}'.")


if __name__ == "__main__":
    main()