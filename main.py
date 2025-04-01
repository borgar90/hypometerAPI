# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import time
import requests
import wikipedia
import praw
import os
from dotenv import load_dotenv # Import load_dotenv

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file

# --- Configuration ---
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = "hypeometer"
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

app = FastAPI()

# --- CORS Configuration ---
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simple In-Memory Cache ---
cache = {}
CACHE_DURATION_SECONDS = 60 * 15  # Cache for 15 minutes

# --- Pydantic Models ---
class HypeQuery(BaseModel):
    query: str

class HypeResult(BaseModel):
    query: str
    score: float
    title: str
    snippets: list[str]

# --- Reddit Setup ---
if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )
else:
    reddit = None
    print("Reddit API credentials not found. Reddit functions will be disabled.")

# --- NewsAPI Setup ---
if not NEWSAPI_KEY:
    print("NewsAPI key not found. NewsAPI functions will be disabled.")

# --- API Endpoints ---
@app.post("/api/hype", response_model=HypeResult)
async def get_hype(hype_query: HypeQuery):
    search_term = hype_query.query.lower()
    current_time = time.time()

    # --- Check Cache ---
    if search_term in cache:
        cached_entry = cache[search_term]
        if current_time - cached_entry['timestamp'] < CACHE_DURATION_SECONDS:
            print(f"Returning cached result for '{search_term}'")
            return HypeResult(**cached_entry['data'])
        else:
            print(f"Cache expired for '{search_term}'")
            del cache[search_term]

    print(f"Fetching new data for: {search_term}")

    # --- Data Collection ---
    score, title, snippets = await analyze_hype(search_term)

    result_data = {
        "query": hype_query.query,
        "score": score,
        "title": title,
        "snippets": snippets,
    }

    # --- Store in Cache ---
    cache[search_term] = {'timestamp': current_time, 'data': result_data}
    print(f"Cached result for '{search_term}'")

    print(f"Result for '{search_term}': Score={score}, Title='{title}'")
    return HypeResult(**result_data)

async def analyze_hype(search_term: str):
    score = 0.0
    title = "No Data"
    snippets = []

    # --- Wikipedia ---
    try:
        page = wikipedia.page(search_term, auto_suggest=False)
        view_count = len(page.links)  # Simple proxy for popularity
        score += min(view_count / 100, 20)  # Scale to contribute to final score
        snippets.append(f"Wikipedia links: {view_count}")
        title = "Wikipedia Data"
    except wikipedia.exceptions.PageError:
        snippets.append("Wikipedia page not found.")
    except wikipedia.exceptions.DisambiguationError as e:
        snippets.append(f"Wikipedia disambiguation: {e.options}")

    # --- Reddit ---
    if reddit:
        try:
            search_results = reddit.subreddit("all").search(search_term, limit=10)
            post_count = sum(1 for _ in search_results)
            score += min(post_count * 2, 30)  # Scale to contribute to final score
            snippets.append(f"Reddit posts: {post_count}")
            if post_count > 0:
                title = "Reddit Data"
        except Exception as e:
            snippets.append(f"Reddit error: {e}")

    # --- NewsAPI.org ---
    if NEWSAPI_KEY:
        try:
            url = f"https://newsapi.org/v2/everything?q={search_term}&apiKey={NEWSAPI_KEY}"
            response = requests.get(url)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            news_data = response.json()
            article_count = news_data.get("totalResults", 0)
            score += min(article_count / 10, 50) # Scale to contribute to final score
            snippets.append(f"News articles: {article_count}")
            if article_count > 0:
                title = "News Data"
        except requests.exceptions.RequestException as e:
            snippets.append(f"NewsAPI error: {e}")

    return float(score), title, snippets