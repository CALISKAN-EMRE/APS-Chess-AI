import os
import urllib.request

DEST_DIR = os.path.abspath(r"c:\Users\3mrec\Desktop\chess_bot\stage5_ui\frontend\src\assets\pieces\cburnett")
os.makedirs(DEST_DIR, exist_ok=True)

BASE_URL = "https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/cburnett"

PIECES = [
    "wK.svg", "wQ.svg", "wR.svg", "wB.svg", "wN.svg", "wP.svg",
    "bK.svg", "bQ.svg", "bR.svg", "bB.svg", "bN.svg", "bP.svg"
]

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

print(f"Downloading Cburnett Staunton SVGs to {DEST_DIR}...")

for piece in PIECES:
    url = f"{BASE_URL}/{piece}"
    dest_path = os.path.join(DEST_DIR, piece)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
    print(f"  Saved {piece} ({len(data)} bytes)")

# Attribution and license documentation
ATTRIBUTION = """# Chess Pieces Attribution & License

## Set: Cburnett Staunton Vector Pieces
- **Designer / Artist**: Colin M.L. Burnett (User:Cburnett on Wikipedia / Wikimedia Commons)
- **License**: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0) / GNU General Public License (GPL)
- **Authoritative Sources**:
  - Wikimedia Commons: https://commons.wikimedia.org/wiki/Category:SVG_chess_pieces
  - Lichess: https://github.com/lichess-org/lila/tree/master/public/piece/cburnett

### Usage & Rights
These vector SVG assets are incorporated directly and unmodified from the authoritative repository.
Under the terms of CC BY-SA 3.0, attribution is hereby provided to Colin M.L. Burnett.
All original geometries and aspect ratios are strictly preserved.
"""

with open(os.path.join(DEST_DIR, "ATTRIBUTION.md"), "w", encoding="utf-8") as f:
    f.write(ATTRIBUTION)

print("Downloaded all 12 piece SVGs and created ATTRIBUTION.md successfully.")
