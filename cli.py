#!/usr/bin/env python3
"""
CLI runner for spotify-shuffler.

Usage:
    python cli.py <source_playlist> [--name "Name"] [-v]
    python cli.py <source_playlist> --into <existing_playlist> [-v]
"""

import argparse
import logging
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from spotify_shuffler import SCOPES, parse_playlist_id, shuffle_playlist

logger = logging.getLogger(__name__)


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
        help="Write shuffle into this existing playlist (URL or ID) instead of creating a new one.",
    )
    parser.add_argument(
        "--name",
        "-n",
        default=None,
        help="Name for the new shuffled playlist (default: '<source name> (shuffled)')",
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
        logger.exception("Spotify API error: %s", e)
        print(f"Spotify API error: {e}", file=sys.stderr)
        if "403" in str(e):
            print(
                "\nForbidden (403) — try these:\n"
                "  1. Delete cached token and re-authorize:\n"
                "       rm .spotify_token_cache\n"
                "  2. Add your Spotify account email in the Developer Dashboard → your app → User management.",
                file=sys.stderr,
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
