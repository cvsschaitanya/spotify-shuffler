"""
Streamlit web app for Spotify playlist shuffling.

Run locally:
    streamlit run app.py

Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env or environment.
Set SPOTIFY_REDIRECT_URI to this app's URL (e.g. http://127.0.0.1:8501).
"""

import os
import urllib.parse

import requests
import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import spotipy

from spotify_shuffler import SCOPES, get_user_playlists, shuffle_playlist

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8501")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def build_auth_url() -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_spotify_client() -> spotipy.Spotify:
    return spotipy.Spotify(auth=st.session_state["access_token"])


# ---------------------------------------------------------------------------
# OAuth callback handling — runs before any UI renders
# ---------------------------------------------------------------------------


def handle_oauth_callback() -> None:
    """Check for ?code= in the URL and exchange it for a token."""
    if "access_token" in st.session_state:
        return

    code = st.query_params.get("code")
    if not code:
        return

    try:
        token_data = exchange_code_for_token(code)
        st.session_state["access_token"] = token_data["access_token"]
        st.session_state["refresh_token"] = token_data.get("refresh_token")
        # Clean the URL so the code isn't reused on refresh
        st.query_params.clear()
    except Exception as e:
        st.error(f"Failed to exchange auth code: {e}")
        st.query_params.clear()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def show_login() -> None:
    st.markdown("Connect your Spotify account to get started.")
    auth_url = build_auth_url()
    st.link_button("Connect Spotify", auth_url, type="primary")


def show_app() -> None:
    sp = get_spotify_client()

    try:
        user = sp.current_user()
    except spotipy.SpotifyException:
        st.error("Session expired. Please reconnect.")
        for key in ("access_token", "refresh_token"):
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown(f"Logged in as **{user['display_name']}**")

    if st.button("Disconnect", type="secondary"):
        for key in ("access_token", "refresh_token", "playlists"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()

    # Load playlists (cached in session)
    if "playlists" not in st.session_state:
        with st.spinner("Loading your playlists..."):
            st.session_state["playlists"] = get_user_playlists(sp)

    playlists = st.session_state["playlists"]
    if not playlists:
        st.warning("No playlists found on your account.")
        return

    if st.button("Refresh playlists"):
        with st.spinner("Refreshing..."):
            st.session_state["playlists"] = get_user_playlists(sp)
            st.rerun()

    playlist_labels = [f"{p['name']}  ({p['tracks_total']} tracks)" for p in playlists]

    source_idx = st.selectbox(
        "Source playlist",
        range(len(playlists)),
        format_func=lambda i: playlist_labels[i],
    )
    source = playlists[source_idx]

    mode = st.radio("Destination", ["Create new playlist", "Shuffle into existing playlist"], horizontal=True)

    target_id = None
    new_name = None

    if mode == "Create new playlist":
        new_name = st.text_input("New playlist name", value=f"{source['name']} (shuffled)")
    else:
        other_playlists = [p for p in playlists if p["id"] != source["id"]]
        if not other_playlists:
            st.warning("No other playlists to shuffle into.")
            return
        other_labels = [f"{p['name']}  ({p['tracks_total']} tracks)" for p in other_playlists]
        target_idx = st.selectbox(
            "Target playlist (contents will be replaced)",
            range(len(other_playlists)),
            format_func=lambda i: other_labels[i],
        )
        target_id = other_playlists[target_idx]["id"]
        target_name = other_playlists[target_idx]["name"]
        st.warning(
            f"⚠️ This will **replace all tracks** in **{target_name}**. "
            "The existing contents of that playlist will be lost."
        )

    if st.button("Shuffle!", type="primary"):
        with st.spinner("Shuffling and uploading..."):
            try:
                url = shuffle_playlist(sp, source["id"], target_id, new_name)
                st.success(f"Done! [Open playlist]({url})")
                # Refresh playlists so new one appears
                st.session_state.pop("playlists", None)
            except ValueError as e:
                st.error(str(e))
            except spotipy.SpotifyException as e:
                st.error(f"Spotify error: {e}")


def main() -> None:
    st.set_page_config(page_title="Spotify Shuffler", page_icon="🔀", layout="centered")
    st.title("🔀 Spotify Shuffler")
    st.caption("True random shuffle for your Spotify playlists")

    if not CLIENT_ID or not CLIENT_SECRET:
        st.error(
            "Missing `SPOTIFY_CLIENT_ID` or `SPOTIFY_CLIENT_SECRET`. "
            "Set them in environment variables or a `.env` file."
        )
        return

    handle_oauth_callback()

    if "access_token" in st.session_state:
        show_app()
    else:
        show_login()


if __name__ == "__main__":
    main()
