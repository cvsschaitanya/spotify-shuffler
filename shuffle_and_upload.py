#!/usr/bin/env python3
"""
Create a true random shuffle of a Spotify playlist and upload it as a new playlist.

Usage:
    python shuffle_and_upload.py <source_playlist> [--name "Name"] [-v]
    python shuffle_and_upload.py <source_playlist> --into <existing_playlist> [-v]   # write into existing, no create

Requires environment variables (or .env):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REDIRECT_URI  (e.g. http://127.0.0.1:8765/callback)
  or SPOTIFY_REDIRECT_PORT  (e.g. 8765) if only port differs from default

First run will open a browser for Spotify login and cache the token.
"""

import argparse
import logging
import os
import random
import re
import sys

# Load .env if present (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)


# Scopes: read source playlist (including private/collab), create/write playlists.
# Create and write use the same scopes (playlist-modify-public, playlist-modify-private).
SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]


def parse_playlist_id(playlist_url_or_id: str) -> str:
    """Extract Spotify playlist ID from URL or return as-is if already an ID."""
    # Spotify playlist URL: https://open.spotify.com/playlist/<id>
    match = re.search(r"(?:playlist/|^)([a-zA-Z0-9]{22})(?:\?|$)", playlist_url_or_id)
    if match:
        pid = match.group(1)
        logger.debug("Parsed playlist ID %s from URL", pid)
        return pid
    if re.fullmatch(r"[a-zA-Z0-9]{22}", playlist_url_or_id):
        return playlist_url_or_id
    raise ValueError(
        f"Invalid playlist URL or ID: {playlist_url_or_id!r}. "
        "Use a Spotify playlist link or the 22-character playlist ID."
    )


def get_all_track_uris(sp: spotipy.Spotify, playlist_id: str) -> list[str]:
    """Fetch all track URIs from a playlist (handles pagination). Skips local/unavailable tracks."""
    uris: list[str] = []
    response = sp.playlist_tracks(playlist_id, limit=50)
    page = 1
    while True:
        batch = response.get("items", [])
        for item in batch:
            track = item.get("track") or item.get("item")
            if not track or item.get("is_local"):
                continue
            uri = track.get("uri")
            if uri:
                uris.append(uri)
        logger.debug("Fetched page %d: %d tracks (total so far: %d)", page, len(batch), len(uris))
        if not response.get("next"):
            break
        response = sp.next(response)
        page += 1
    logger.info("Fetched %d track(s) from source playlist", len(uris))
    return uris


def fetch_and_shuffle(sp: spotipy.Spotify, source_playlist_id: str) -> tuple[list[str], str]:
    """Fetch all tracks from a playlist and return them shuffled, along with the playlist name."""
    logger.info("Loading source playlist %s", source_playlist_id)
    try:
        pl = sp.playlist(source_playlist_id)
        source_name = pl.get("name", "Playlist")
        logger.debug("Source playlist name: %s", source_name)
    except Exception as e:
        logger.warning("Could not get playlist name: %s", e)
        source_name = "Playlist"

    track_uris = get_all_track_uris(sp, source_playlist_id)
    if not track_uris:
        raise SystemExit("No tracks found in the source playlist (or all are local/unavailable).")

    logger.info("Shuffling %d track(s)", len(track_uris))
    random.shuffle(track_uris)
    return track_uris, source_name


def write_tracks(sp: spotipy.Spotify, playlist_id: str, track_uris: list[str], *, replace: bool) -> None:
    """Write tracks into a playlist, either replacing all contents or appending."""
    batch_size = 100
    if replace:
        logger.info("Replacing playlist %s contents (%d tracks)", playlist_id, len(track_uris))
        sp.playlist_replace_items(playlist_id, track_uris[:batch_size])
        remaining = track_uris[batch_size:]
    else:
        remaining = track_uris

    num_batches = (len(remaining) + batch_size - 1) // batch_size
    for i in range(0, len(remaining), batch_size):
        batch = remaining[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        sp.playlist_add_items(playlist_id, batch)
        logger.info("Added tracks batch %d/%d (%d tracks)", batch_num, num_batches, len(batch))


def shuffle_playlist(
    sp: spotipy.Spotify,
    source_playlist_id: str,
    target_playlist_id: str | None = None,
    new_playlist_name: str | None = None,
) -> str:
    """Shuffle a playlist's tracks into a new or existing playlist. Returns the result playlist URL."""
    track_uris, source_name = fetch_and_shuffle(sp, source_playlist_id)

    if target_playlist_id:
        write_tracks(sp, target_playlist_id, track_uris, replace=True)
        url = sp.playlist(target_playlist_id)["external_urls"]["spotify"]
        logger.info("Done. Updated playlist: %s", url)
    else:
        name = new_playlist_name or f"{source_name} (shuffled)"
        logger.info("Creating playlist %r", name)
        new_pl = sp.current_user_playlist_create(name, public=True, description="True random shuffle.")
        write_tracks(sp, new_pl["id"], track_uris, replace=False)
        url = new_pl["external_urls"]["spotify"]
        logger.info("Done. New playlist: %s", url)

    return url


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shuffle a Spotify playlist and upload it as a new playlist (or into an existing one)."
    )
    parser.add_argument(
        "playlist",
        help="Source playlist URL or ID to shuffle",
    )
    parser.add_argument(
        "--into",
        "-i",
        metavar="PLAYLIST",
        default=None,
        help="Write shuffle into this existing playlist (URL or ID) instead of creating a new one. Uses only write scope.",
    )
    parser.add_argument(
        "--name",
        "-n",
        default=None,
        help="Name for the new shuffled playlist when not using --into (default: '<source name> (shuffled)')",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from third-party libs unless verbose
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("spotipy").setLevel(logging.WARNING)

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI")
    if not redirect_uri:
        port = os.environ.get("SPOTIFY_REDIRECT_PORT", "8765")
        redirect_uri = f"http://127.0.0.1:{port}/callback"

    if not client_id or not client_secret:
        logger.error("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET")
        print(
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET (and optionally SPOTIFY_REDIRECT_URI).\n"
            "  • In the environment, or\n"
            "  • In a .env file (copy .env.example to .env and fill in).\n"
            "  Get credentials from https://developer.spotify.com/dashboard",
            file=sys.stderr,
        )
        sys.exit(1)

    logger.debug("Using redirect_uri: %s", redirect_uri)

    try:
        source_playlist_id = parse_playlist_id(args.playlist)
        logger.info("Source playlist ID: %s", source_playlist_id)
    except ValueError as e:
        logger.error("Invalid playlist input: %s", e)
        print(e, file=sys.stderr)
        sys.exit(1)

    target_playlist_id = None
    if args.into:
        try:
            target_playlist_id = parse_playlist_id(args.into)
            logger.info("Target playlist (--into): %s", target_playlist_id)
        except ValueError as e:
            logger.error("Invalid --into playlist: %s", e)
            print(e, file=sys.stderr)
            sys.exit(1)

    logger.debug("Initializing Spotify OAuth")
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=".spotify_token_cache",
    )
    sp = spotipy.Spotify(auth_manager=auth)

    try:
        url = shuffle_playlist(sp, source_playlist_id, target_playlist_id, args.name)
        print(f"Shuffled playlist: {url}")
    except spotipy.SpotifyException as e:
        err_str = str(e)
        logger.exception("Spotify API error: %s", e)
        print(f"Spotify API error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
