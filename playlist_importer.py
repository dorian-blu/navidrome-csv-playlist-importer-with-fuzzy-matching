import requests
import hashlib
import time
import random
import string
from fuzzywuzzy import fuzz
import re
import sys
import os
import csv

# --- Configuration (UPDATE THESE VALUES) ---
# Your Navidrome server's full address (e.g., "http://192.168.1.10:4533").
NAVIDROME_URL = "http://YOUR_NAVIDROME_IP:4533"
# The username for your Navidrome account.
NAVIDROME_USER = "your_navidrome_username"
# Your simple Navidrome user password.
NAVIDROME_TOKEN = "your_navidrome_password"
# The absolute path to the folder where your CSV files are stored.
CSV_FILE_PATH = "/path/to/your/csv/folder/"
# A name for your script, which Navidrome's API will see.
SUBSONIC_CLIENT_NAME = "PlaylistImporter"


# --- Default Fallback Configuration ---
# These values are used if no command-line flags are provided.
DEFAULT_CSV_FILE_NAME = None
DEFAULT_PLAYLIST_NAME = "My Imported Playlist"


# --- Default Fuzzy Matching Thresholds ---
# These are used if no matching flags are provided on the command line.
# Values are percentages (0-100). Higher is stricter.
DEFAULT_FUZZY_TITLE_THRESHOLD = 70
DEFAULT_FUZZY_ARTIST_THRESHOLD = 85
DEFAULT_FUZZY_ALBUM_THRESHOLD = 30


# --- Subsonic API Helper Functions ---
def _get_subsonic_auth_params(username, password):
    """Generates the required authentication parameters for a Subsonic API call."""
    salt = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    token = hashlib.md5((password + salt).encode('utf-8')).hexdigest()
    return {
        "u": username, "t": token, "s": salt, "v": "1.16.1", "c": SUBSONIC_CLIENT_NAME, "f": "json"
    }

def _make_subsonic_request(endpoint, extra_params=None):
    """Makes a request to a Subsonic API endpoint."""
    auth_params = _get_subsonic_auth_params(NAVIDROME_USER, NAVIDROME_TOKEN)
    all_params = auth_params
    if extra_params:
        all_params.update(extra_params)
    url = f"{NAVIDROME_URL}/rest/{endpoint}"
    try:
        response = requests.get(url, params=all_params, timeout=15)
        response.raise_for_status()
        json_response = response.json()
        if 'subsonic-response' in json_response and json_response['subsonic-response']['status'] == 'failed':
            error_msg = json_response['subsonic-response']['error']['message']
            print(f"ERROR: Subsonic API error for {endpoint}: {error_msg}")
            return None
        return json_response.get('subsonic-response')
    except requests.exceptions.RequestException as e:
        print(f"ERROR: An API request failed for {url}: {e}")
    except requests.exceptions.JSONDecodeError:
        print(f"ERROR: Failed to decode JSON from response. Raw text:\n{response.text}")
    return None

def ping_navidrome():
    """Tests connection and authentication with the Subsonic API."""
    print("\n[PING] Testing connection to Navidrome via Subsonic API...")
    response = _make_subsonic_request("ping.view")
    if response and response.get('status') == 'ok':
        print("[PING] SUCCESS: Connection and authentication successful!")
        return True
    else:
        print("[PING] FAILURE: Could not connect or authenticate. Check URL, user, and password.")
        return False

# --- Core Song Search Logic ---
def _search_song_id(display_artist, album_artist, album, title, title_thresh, artist_thresh, album_thresh):
    """Searches for a song ID with reduced logging."""
    primary_artist = album_artist if album_artist else display_artist
    if not title or not primary_artist:
        return None

    query_string = f"{primary_artist} {title}"
    search_params = {"query": query_string, "songCount": 20, "albumCount": 0, "artistCount": 0}
    response_data = _make_subsonic_request("search3.view", extra_params=search_params)

    if not response_data or 'searchResult3' not in response_data or 'song' not in response_data.get('searchResult3', {}):
        return None
    
    search_results = response_data['searchResult3']['song']

    best_match_id = None
    highest_combined_score = -1.0
    best_match_details = ""

    for song in search_results:
        nd_title = song.get("title", "").lower().strip()
        nd_artist = song.get("artist", "").lower().strip()
        nd_album = song.get("album", "").lower().strip()

        title_score = fuzz.ratio(title, nd_title)
        artist_score = fuzz.partial_ratio(primary_artist, nd_artist)
        album_score = fuzz.ratio(album, nd_album)

        if (title_score < title_thresh or artist_score < artist_thresh):
            continue

        combined_score = (artist_score * 0.40) + (title_score * 0.40) + (album_score * 0.20)

        if combined_score > highest_combined_score:
            highest_combined_score = combined_score
            best_match_id = song.get("id")
            best_match_details = f"'{nd_artist} - {nd_title}' (Album: '{nd_album}')"

    if best_match_id:
        print(f"  -> Matched with: {best_match_details}")
        print(f"  -> Combined Score: {highest_combined_score:.2f}")
        return best_match_id
    else:
        return None

# --- Playlist Management Functions ---
def get_or_create_playlist(name):
    """Checks if a playlist exists. If not, it creates it. Returns the playlist ID."""
    print(f"\n[PLAYLIST] Checking for playlist named '{name}'...")
    response = _make_subsonic_request("getPlaylists.view")
    if response and 'playlists' in response and 'playlist' in response['playlists']:
        for pl in response['playlists']['playlist']:
            if pl.get('name') == name:
                playlist_id = pl.get('id')
                print(f"[PLAYLIST] Found existing playlist. ID: {playlist_id}")
                return playlist_id
    
    print(f"[PLAYLIST] No playlist named '{name}' found. Creating it now...")
    create_params = {"name": name}
    create_response = _make_subsonic_request("createPlaylist.view", extra_params=create_params)
    if create_response and 'playlist' in create_response:
        playlist_id = create_response['playlist'].get('id')
        print(f"[PLAYLIST] Successfully created playlist. ID: {playlist_id}")
        return playlist_id
    print(f"ERROR: Failed to create playlist '{name}'.")
    return None

def add_songs_to_playlist(playlist_id, song_ids):
    """Adds a list of song IDs to a given playlist."""
    if not song_ids:
        print("\n[PLAYLIST] No new songs were found to add.")
        return False
    print(f"\n[PLAYLIST] Adding {len(song_ids)} song(s) to playlist ID {playlist_id}...")
    update_params = {"playlistId": playlist_id, "songIdToAdd": song_ids}
    response = _make_subsonic_request("updatePlaylist.view", extra_params=update_params)
    if response and response.get('status') == 'ok':
        print("[PLAYLIST] Successfully added songs to the playlist.")
        return True
    else:
        print("ERROR: Failed to add songs to the playlist.")
        return False

# --- Helper Functions ---
def clean_text(text):
    """Performs basic cleaning on a text string."""
    if not text: return ""
    text = re.sub(r'\.(mp3|flac|m4a|ogg|wav|aiff|wma|aac|alac|ape|dsf)$', '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()

def advanced_clean_title(title, artist):
    """Performs advanced cleaning on a song title."""
    if not title: return ""
    cleaned_title = re.sub(r'[.,;:\-?!]', ' ', title)
    cleaned_title = re.sub(r'(^|\s)[a-zA-Z]?\d+[\s.-]+', ' ', cleaned_title, flags=re.IGNORECASE)
    cleaned_title = re.sub(r'\[.*?\]|\(.*?\)|\{.*?\}', '', cleaned_title)
    if artist:
        cleaned_title = re.sub(r'\b' + re.escape(artist) + r'\b', '', cleaned_title, flags=re.IGNORECASE)
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title).strip()
    return cleaned_title

def load_songs_from_csv(full_path):
    """Loads song data from a specified CSV file."""
    print(f"\n[CSV] Loading songs from: {full_path}")
    if not os.path.exists(full_path):
        print(f"[CSV] ERROR: File not found at '{full_path}'.")
        return []
    songs_to_process = []
    try:
        with open(full_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                song_data = {
                    "title": row.get('Track', ''),
                    "artist": row.get('Artist', ''),
                    "album_artist": row.get('Album Artist', ''),
                    "album": row.get('Album', '')
                }
                if not song_data['title'] or not song_data['artist']:
                    print(f"[CSV] WARNING: Skipping row {i+2} due to missing Track or Artist.")
                    continue
                songs_to_process.append(song_data)
        print(f"[CSV] Successfully loaded {len(songs_to_process)} songs from the CSV.")
        return songs_to_process
    except Exception as e:
        print(f"[CSV] ERROR: An error occurred while reading the CSV file: {e}")
        return []

# --- Main Execution ---
if __name__ == "__main__":
    # Set variables from default configuration
    csv_file_name = DEFAULT_CSV_FILE_NAME
    target_playlist_name = DEFAULT_PLAYLIST_NAME
    title_threshold = DEFAULT_FUZZY_TITLE_THRESHOLD
    artist_threshold = DEFAULT_FUZZY_ARTIST_THRESHOLD
    album_threshold = DEFAULT_FUZZY_ALBUM_THRESHOLD
    apply_advanced_cleaning = False
    
    # Override with command-line arguments if they exist
    for arg in sys.argv[1:]:
        arg_lower = arg.lower()
        if arg_lower.startswith('-importfile:'):
            csv_file_name = arg.split(':', 1)[1].strip('"')
        elif arg_lower.startswith('-playlistname:'):
            target_playlist_name = arg.split(':', 1)[1].strip('"')
        elif arg_lower.startswith('-titlematch:'):
            try: title_threshold = int(arg.split(':', 1)[1])
            except (ValueError, IndexError): print(f"WARNING: Invalid value for -titlematch. Using default: {title_threshold}")
        elif arg_lower.startswith('-artistmatch:'):
            try: artist_threshold = int(arg.split(':', 1)[1])
            except (ValueError, IndexError): print(f"WARNING: Invalid value for -artistmatch. Using default: {artist_threshold}")
        elif arg_lower.startswith('-albummatch:'):
            try: album_threshold = int(arg.split(':', 1)[1])
            except (ValueError, IndexError): print(f"WARNING: Invalid value for -albummatch. Using default: {album_threshold}")
        elif arg_lower.startswith('-cleantitle:'):
            if arg.split(':', 1)[1].strip('"').lower() == 'true':
                apply_advanced_cleaning = True

    # --- Validation ---
    if not csv_file_name:
        script_name = os.path.basename(sys.argv[0])
        print("\nERROR: No input CSV file specified.")
        print(f"Usage: python3 {script_name} -importfile:\"playlist.csv\" [optional flags]")
        sys.exit(1)

    print("--- Starting Playlist Import ---")
    print(f"      Import File: {csv_file_name}")
    print(f"  Target Playlist: {target_playlist_name}")
    print(f" Fuzzy Thresholds: Title={title_threshold}, Artist={artist_threshold}, Album={album_threshold}")
    print(f"  Title Cleaning: {'Enabled' if apply_advanced_cleaning else 'Disabled'}")

    if not ping_navidrome():
        sys.exit(1)

    full_csv_path = os.path.join(CSV_FILE_PATH, csv_file_name)
    songs_to_match = load_songs_from_csv(full_csv_path)
    if not songs_to_match:
        print("CRITICAL: No songs loaded from CSV. Exiting.")
        sys.exit(1)

    playlist_id = get_or_create_playlist(target_playlist_name)
    if not playlist_id:
        print("CRITICAL: Could not get or create the playlist. Exiting.")
        sys.exit(1)
        
    found_song_ids = []
    unmatched_songs = []
    
    print("\n--- Starting Song Matching ---")
    for song_data in songs_to_match:
        artist_cleaned = clean_text(song_data["artist"])
        album_artist_cleaned = clean_text(song_data.get("album_artist") or artist_cleaned)
        album_cleaned = clean_text(song_data["album"])
        title_to_match = clean_text(song_data["title"])

        if apply_advanced_cleaning:
            title_to_match = advanced_clean_title(title_to_match, artist_cleaned)

        print(f"\nArtist: '{artist_cleaned}', Album: '{album_cleaned}', Title: '{title_to_match}'")
        
        found_id = _search_song_id(
            artist_cleaned, album_artist_cleaned, album_cleaned, title_to_match,
            title_threshold, artist_threshold, album_threshold
        )
        
        if found_id:
            found_song_ids.append(found_id)
        else:
            unmatched_songs.append(f"- Artist: '{artist_cleaned}', Title: '{title_to_match}'")
    
    add_songs_to_playlist(playlist_id, found_song_ids)
    
    if unmatched_songs:
        print(f"\n--- Songs Without a Match ({len(unmatched_songs)}) ---")
        for item in unmatched_songs:
            print(item)
    
    # --- Final Statistics ---
    print("\n--- Import Summary ---")
    print(f"  Total Tracks Attempted: {len(songs_to_match)}")
    print(f"          Tracks Matched: {len(found_song_ids)}")
    print(f"        Tracks Unmatched: {len(unmatched_songs)}")

    print("\n--- Playlist Import Finished ---")
