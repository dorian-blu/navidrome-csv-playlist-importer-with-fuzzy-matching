# navidrome-csv-playlist-importer-with-fuzzy-matching

# Navidrome Playlist Importer
A Python script to import songs from a CSV file into a Navidrome music server playlist. It uses fuzzy matching to find songs even if the metadata isn't a perfect match and includes advanced options for cleaning up messy track titles.

## Features
- CSV to Playlist: Imports songs from a CSV file into a new or existing Navidrome playlist.
- Fuzzy Matching: Intelligently finds songs even with minor differences in artist, album, or track titles.
- Advanced Title Cleaning: Optional, powerful cleaning rules to handle messy metadata before matching.
- Flexible Controls: Use command-line flags to specify the input file, playlist name, and matching sensitivity.

## Setup
### 1. Requirements
This script requires Python 3. You must install the necessary libraries. It's recommended to do this in a virtual environment.

Create a requirements.txt file with the content below and run:
pip install -r requirements.txt

### 2. Configuration
Edit the Python script (playlist_importer.py) and fill in your Navidrome server details at the top of the file:

- NAVIDROME_URL: Your Navidrome server's full address (e.g., "http://192.168.1.10:4533").
- NAVIDROME_USER: The username for your Navidrome account.
- NAVIDROME_TOKEN: Your Navidrome user password.
- CSV_FILE_PATH: The absolute path to the folder where your CSV files are stored (e.g., "/music/playlists/").

## Usage
### 1. CSV File Format
Your input CSV file must have a header row with the following column names:
- Track: The song title.
- Artist: The primary artist of the song.
- Album Artist: The artist for the entire album (can be the same as Artist).
- Album: The name of the album the song is on.

Example my_playlist.csv:
```
Track,Artist,Album Artist,Album
01. too late (remix),Billy Paul,Billy Paul,360 Degrees Of Billy Paul
prowler,Living Legends,Living Legends,Almost There
```
Properly formatted CSVs will enclose fields containing commas in double quotes (e.g., "My Song, Pt. 2",My Artist,...). Most spreadsheet programs handle this automatically.

### 2. Running the Script
Place your CSV file in the folder defined by CSV_FILE_PATH. Navigate to the script's directory in your terminal and run it using command-line flags. The -importfile: flag is mandatory.

## Basic Usage
```python3 playlist_importer.py -importfile:"test.csv"```
(This imports test.csv into the default playlist with default settings.)

## Specify Both File and Playlist
```python3 playlist_importer.py -importfile:"prowler_mix.csv" -playlistname:"Living Legends Mix"```

## Using Advanced Title Cleaning
The `-cleantitle:true` flag enables aggressive cleaning of the song title before matching. This is useful for messy file names. It removes:
- Leading track numbers (e.g., 01., 2 -, A1., B2-). 
- Text in brackets or parentheses (e.g., (Remix), [Live]).
- The artist's name from the title string.

```playlist_importer.py -importfile:"messy_tags.csv" -playlistname:"Cleaned Playlist" -cleantitle:true```

## Full Example with All Flags
You can customize the fuzzy matching sensitivity (0-100). Higher is stricter. Testing showed solid results down to 40% fuzz rate for artist and title matching.

```python3 playlist_importer.py -importfile:"mix.csv" -playlistname:"My Mix" -titlematch:65 -artistmatch:80 -cleantitle:true```
