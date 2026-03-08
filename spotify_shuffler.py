"""
Core library for Spotify playlist shuffling.

Provides functions for parsing playlist IDs/URLs, fetching tracks,
shuffling, writing tracks, and listing user playlists.
"""

import logging
import random
import re

import spotipy

logger = logging.getLogger(__name__)

SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
]


def parse_playlist_id(playlist_url_or_id: str) -> str:
    """Extract Spotify playlist ID from URL or return as-is if already an ID."""
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
        raise ValueError("No tracks found in the source playlist (or all are local/unavailable).")

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


def get_user_playlists(sp: spotipy.Spotify) -> list[dict]:
    """Return all playlists for the current user as a list of {id, name, tracks_total, url}."""
    playlists: list[dict] = []
    response = sp.current_user_playlists(limit=50)
    while True:
        for item in response.get("items", []):
            if not item:
                continue
            # "tracks" is deprecated; newer responses use "items" for the count
            count_obj = item.get("tracks") or item.get("items") or {}
            playlists.append({
                "id": item["id"],
                "name": item.get("name", "(untitled)"),
                "tracks_total": count_obj.get("total", 0),
                "url": (item.get("external_urls") or {}).get("spotify", ""),
            })
        if not response.get("next"):
            break
        response = sp.next(response)
    return playlists
