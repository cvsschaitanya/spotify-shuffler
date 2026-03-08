# spotify-shuffler

Create a **true random shuffle** of any Spotify playlist and save it as a new playlist under your account.

## Setup

1. **Spotify app**  
   Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and note:
   - Client ID  
   - Client Secret  

2. **Redirect URI**  
   In the app settings, add a Redirect URI (default: `http://127.0.0.1:8765/callback`). Use `127.0.0.1`, not `localhost`—Spotify treats only loopback IPs as secure for HTTP. If port 8765 is in use, set `SPOTIFY_REDIRECT_PORT=8889` (or any free port) and add that URL in the Dashboard too.

3. **Virtual environment and dependencies**  
   Create a venv and install dependencies:

   ```bash
   uv venv          # creates .venv (only if not already present)
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

   Or with `uv` only: `uv run shuffle_and_upload.py ...` (uses `.venv` if present).

4. **Credentials**  
   Set environment variables:

   ```bash
   export SPOTIFY_CLIENT_ID="your_client_id"
   export SPOTIFY_CLIENT_SECRET="your_client_secret"
   export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8765/callback"   # optional; or SPOTIFY_REDIRECT_PORT=8765
   ```

   Or use a `.env` file in the project root (with `python-dotenv` installed):

   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8765/callback
   ```

## Usage

Activate the venv first (or use `uv run`):

```bash
source .venv/bin/activate

# From playlist URL
python shuffle_and_upload.py "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# From playlist ID
python shuffle_and_upload.py 37i9dQZF1DXcBWIGoYBM5M

# Custom name for the new playlist
python shuffle_and_upload.py "https://open.spotify.com/playlist/..." --name "My random mix"
```

The first run opens a browser for Spotify login; the token is cached for later runs. The script fetches all tracks from the source playlist, shuffles them with Python’s `random.shuffle`, creates a new playlist under your account, and adds the shuffled tracks.

## Git (personal machine with work credentials)

To push using a personal SSH key instead of the default:

```bash
git config core.sshCommand "ssh -i ~/.ssh/id_ed25519_personal"
```