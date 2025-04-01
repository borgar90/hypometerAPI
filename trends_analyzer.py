# trends_analyzer.py
import pandas as pd
from pytrends.request import TrendReq
import time # To add slight delays if needed

def get_google_trends_data(keyword: str, timeframe='today 1-m'):
    """
    Fetches Google Trends data for a specific keyword.
    Args:
        keyword (str): The search term.
        timeframe (str): Timeframe for trends (e.g., 'now 7-d', 'today 1-m', 'today 3-m').
                           See pytrends docs for formats.
    Returns:
        dict: Contains interest_over_time DataFrame, related queries,
              or None if an error occurs.
    """
    pytrends = TrendReq(hl='en-US', tz=360) # hl=host language, tz=timezone offset

    try:
        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo='', gprop='')
        # Add a small delay to avoid hitting rate limits too quickly if making many requests
        time.sleep(0.5)

        interest_df = pytrends.interest_over_time()
        # Check if the keyword column exists and has data
        if keyword not in interest_df.columns or interest_df[keyword].sum() == 0:
             print(f"No sufficient Google Trends data found for '{keyword}' in timeframe '{timeframe}'.")
             # Return structure indicating no data or low data
             return {"interest": pd.DataFrame(), "related_queries": {}} # Return empty structures


        # Add a small delay
        time.sleep(0.5)
        related_queries_dict = pytrends.related_queries()

        return {
            "interest": interest_df,
            "related_queries": related_queries_dict.get(keyword, {}) # Get data specific to the keyword
        }

    except Exception as e:
        # A common issue is a '429 - Too Many Requests' response.
        # Implement proper error handling/logging here.
        print(f"Error fetching Google Trends data for '{keyword}': {e}")
        # Consider more specific error handling based on exception type
        return None


def calculate_hype_from_trends(trends_data: dict):
    """
    Calculates a hype score and title based on Google Trends data.
    Args:
        trends_data (dict): The dictionary returned by get_google_trends_data.
    Returns:
        tuple: (score: float, title: str, snippets: list[str])
    """
    if not trends_data or trends_data["interest"].empty:
        return 0.0, "No Data", ["Could not retrieve sufficient trend data."]

    interest_df = trends_data["interest"]
    related_queries = trends_data["related_queries"]

    # --- Score Calculation (Example) ---
    # Use the most recent interest value as the score.
    # Google Trends scores are relative (0-100), 100 being peak popularity
    # for that term in the given timeframe/region.
    # Exclude the 'isPartial' column if present
    keyword_column = [col for col in interest_df.columns if col != 'isPartial'][0]
    score = interest_df[keyword_column].iloc[-1] if not interest_df.empty else 0


    # --- Title Mapping (Example) ---
    title = "Unknown"
    if score > 85: title = "Peak Interest!"
    elif score > 65: title = "High Interest"
    elif score > 40: title = "Moderate Interest"
    elif score > 15: title = "Low Interest"
    else: title = "Minimal Interest"
    if score == 0 and interest_df[keyword_column].sum() > 0:
         title = "Interest Fading?" # If score is 0 now but was non-zero previously


    # --- Snippets from Related Queries ---
    snippets = []
    if related_queries:
        if 'top' in related_queries and related_queries['top'] is not None:
             snippets.extend([f"Top related: {row['query']}" for index, row in related_queries['top'].head(2).iterrows()])
        if 'rising' in related_queries and related_queries['rising'] is not None:
             snippets.extend([f"Rising related: {row['query']} (+{row['value']}%)" for index, row in related_queries['rising'].head(3).iterrows()])

    if not snippets:
        snippets.append("No specific related queries found.")


    return float(score), title, snippets