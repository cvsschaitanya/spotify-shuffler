# spotify-shuffler

True random shuffle for Spotify playlists — as a **web app** (Streamlit) or **CLI**.

## Setup

1. **Spotify app**
   Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and note:
   - Client ID
   - Client Secret

2. **Redirect URIs**
   In the app settings, add the redirect URIs you need:
   - **Web app** (local): `http://127.0.0.1:8501`
   - **Web app** (deployed): `https://your-app.streamlit.app`
   - **CLI**: `http://127.0.0.1:8765/callback`

3. **Virtual environment and dependencies**

   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

4. **Credentials**
   Create a `.env` file (or export):

   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8501
   ```

## Web app (Streamlit)

```bash
streamlit run app.py
```

Open `http://127.0.0.1:8501`, click **Connect Spotify**, pick a playlist, and shuffle.

Set `SPOTIFY_REDIRECT_URI` to the app's URL (e.g. `http://127.0.0.1:8501` locally, or your deployed URL).

## CLI

```bash
# Set redirect URI for CLI callback
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8765/callback"

# Shuffle into a new playlist
python cli.py "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# Custom name
python cli.py "https://open.spotify.com/playlist/..." --name "My random mix"

# Shuffle into an existing playlist
python cli.py "https://open.spotify.com/playlist/SOURCE" --into "https://open.spotify.com/playlist/TARGET"

# Verbose logging
python cli.py "https://open.spotify.com/playlist/..." -v
```

## Project structure

```
spotify_shuffler.py   # Core library (parse, fetch, shuffle, write)
cli.py                # CLI runner
app.py                # Streamlit web app
requirements.txt
.env                  # Credentials (not committed)
```

## Git (personal machine with work credentials)

To push using a personal SSH key instead of the default:

```bash
git config core.sshCommand "ssh -i ~/.ssh/id_ed25519_personal"
```
