import os
import json
from apify_client import ApifyClient
import streamlit as st

APIFY_TOKEN = st.secrets["api"]["APIFY_TOKEN"]
client = ApifyClient(APIFY_TOKEN)

def get_download_url(reel_url):
    """Fetch video download URL using Apify actor Fj1zYgto86GELL443"""
    try:
        run_input = {
            "links": [reel_url],
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        run = client.actor("Fj1zYgto86GELL443").call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if items:
            m4a_url = items[0].get("result", {}).get("medias")[1].get("url")
            video_url = items[0].get("result", {}).get("medias")[0].get("url")
            
            return m4a_url, video_url
    except Exception as e:
        print(f"Error fetching download URL for {reel_url}: {e}")
    return None, None

def fetch_instagram_reels(username: str, limit: int = 20):
    if not APIFY_TOKEN:
        st.error("APIFY_TOKEN not set in environment variables.")
        return []

    client = ApifyClient(token=APIFY_TOKEN)

    input_data = {
        'usernames': [username],
        'maxItems': limit
    }

    try:
        run = client.actor('NNyHXtFNu84OQyAz2').call(run_input=input_data, timeout_secs=1000)
    except Exception as e:
        if "Invalid token" in str(e) or "subscription" in str(e).lower():
            st.error("APIFY token is invalid, expired, or your subscription has expired. Please renew or update your API key.")
        else:
            st.error(f"Error running the actor: {e}")
        return []

    dataset_id = run.get('defaultDatasetId')
    if not dataset_id:
        st.warning("No dataset found for this run.")
        return []

    try:
        dataset_items = client.dataset(dataset_id).list_items().items
    except Exception as e:
        st.error(f"Failed to fetch dataset items: {e}")
        return []

    return dataset_items

def extract_and_save_reel_data(reels, username=None):
    """
    Filters reels with ≥1M views, adds download URLs, and returns as list.
    No file read/write occurs.
    """
    filtered_data = []

    for reel in reels:
        code = reel.get('code')
        if not code:
            continue

        url = f"https://www.instagram.com/p/{code}/"
        play_count = reel.get('play_count') or 0

        if play_count < 1_000_000:
            continue

        m4a_url, video_url = get_download_url(url)

        reel_data = {
            "url": url,
            "comment_count": reel.get('comment_count', 0),
            "like_count": reel.get('like_count', 0),
            "play_count": play_count,
            "m4a_url": m4a_url,
            "video_url": video_url,
            "script": "",
            "subtitles": "",
            "visual_description": "",
        }

        filtered_data.append(reel_data)

    return filtered_data
