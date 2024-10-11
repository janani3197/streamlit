#!/usr/bin/env python
# coding: utf-8

import os
import re
import pandas as pd
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import streamlit as st
import io

# Replace with your own API key
API_KEY = "AIzaSyDLaW8LSyDsUprS9ZudkoqmXZFPtOsMBFQ"

def youtube_search(query, max_results=10, published_after=None):
    """Search for videos on YouTube."""
    youtube = build("youtube", "v3", developerKey=API_KEY)
    
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=max_results,
        type="video",  # Only return video results
        publishedAfter=published_after  # Filter by published date if provided
    ).execute()

    video_links = []
    for item in search_response.get("items", []):
        video_id = item["id"]["videoId"]
        video_title = item["snippet"]["title"]
        video_link = f"https://www.youtube.com/watch?v={video_id}"
        date_posted = item["snippet"]["publishedAt"].split("T")[0]  # Extract date without timestamp
        video_links.append((video_id, video_title, video_link, date_posted))

    return video_links

def get_comments(video_id, max_comments=10):
    """Retrieve the last N comments for a given video ID."""
    youtube = build("youtube", "v3", developerKey=API_KEY)
    comments = []
    page_token = None
    
    try:
        while len(comments) < max_comments:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                textFormat="plainText",
                maxResults=min(max_comments - len(comments), 100),  # Adjust to not exceed max_comments
                order='time',
                pageToken=page_token
            ).execute()

            # Fetch comments and format them with numbering
            for idx, item in enumerate(response.get("items", [])):
                comment = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(f"{len(comments) + 1}. {comment}")  # Format with numbering
            
            # Check if there are more comments to fetch
            page_token = response.get("nextPageToken")
            if not page_token:  # Exit if there are no more pages
                break

    except HttpError as e:
        if e.resp.status == 403:
            return ["Comments are disabled for this video."]
        else:
            return [f"Error fetching comments: {e}"]

    return comments[:max_comments]  # Return only up to max_comments

def download_transcript(video_id):
    """
    Download the transcript, translate to English if necessary, and return as a string.
    Args:
        video_id (str): The YouTube video ID.
    Returns:
        str: The transcript text in English or an empty string if an error occurs.
    """
    try:
        # Retrieve available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        transcript = None

        # Try to find a manually created or generated transcript in English first
        try:
            transcript = transcript_list.find_transcript(['en'])
        except:
            try:
                # Fall back to generated transcript if manually created isn't available
                transcript = transcript_list.find_generated_transcript(['en'])
            except:
                # If no English transcript, pick the first available transcript in any language
                for available_transcript in transcript_list:
                    if available_transcript.is_translatable:
                        transcript = available_transcript
                        break
        
        if transcript is None:
            raise Exception("No translatable transcript available")

        # If transcript isn't in English, translate it to English
        if transcript.language_code != 'en':
            transcript = transcript.translate('en')
        
        # Fetch the transcript and format it
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript.fetch())

        # Clean up the transcript by removing timecodes and speaker names
        transcript_text = re.sub(r'\[\d+:\d+:\d+\]', '', transcript_text)
        transcript_text = re.sub(r'<\w+>', '', transcript_text)
        transcript_text = re.sub(r'\s+', ' ', transcript_text).strip()

        return transcript_text
    except Exception as e:
        return ""

def sanitize_filename(filename):
    """Sanitize a filename by removing or replacing invalid characters."""
    # Remove characters that are invalid for filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    sanitized = sanitized.replace(' ', '_')  # Optionally replace spaces with underscores
    return "".join(c for c in sanitized if c.isalnum() or c in ('_', '-')).rstrip()

def main():
    st.title("YouTube Data Fetcher")
    
    user_query = st.text_input("Enter a search term for YouTube:")
    
    num_videos_input = st.number_input("Enter the number of videos to retrieve (or leave blank for maximum):", min_value=1, value=10)
    num_comments_input = st.number_input("Enter the number of comments to retrieve for each video (or leave blank for maximum):", min_value=1, value=10)
    
    years_back = st.number_input("How many years back do you want to search for videos?", min_value=1, value=1)

    if st.button("Search"):
        published_after_date = (datetime.now() - timedelta(days=years_back * 365)).isoformat("T") + "Z"

        # Search for videos
        video_links = youtube_search(user_query, num_videos_input, published_after=published_after_date)

        # Prepare data for DataFrame
        data = []

        if video_links:
            for video_id, title, link, date_posted in video_links:
                # Get last N comments for each video
                comments = get_comments(video_id, num_comments_input)
                comments_text = '\n'.join(comments)  # Join comments into a single string, one per line

                # Get transcript for each video
                transcript_text = download_transcript(video_id)
                transcript_text = transcript_text if transcript_text else "Transcript not available."

                # Append data
                data.append({
                    "Serial Number": len(data) + 1,
                    "Video Name": title,
                    "Video Link": link,
                    "Date Posted": date_posted,
                    "Comments": comments_text,
                    "Transcript": transcript_text
                })

            # Create DataFrame
            df = pd.DataFrame(data)

            # Display the results in the app
            st.dataframe(df)

        else:
            st.warning("No videos found.")

if __name__ == "__main__":
    main()
