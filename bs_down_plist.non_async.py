import requests
import zipfile
from sys import argv
from pathlib import Path

# from dataclasses import dataclass
from itertools import batched

from tqdm import tqdm
import json

BATCH_SIZE_MAX = 50
SAVE_PATH = "./downloads"
API_ENDPOINT = "https://api.beatsaver.com"

SAVE_PATH = Path(SAVE_PATH)
if not SAVE_PATH.is_dir():
    SAVE_PATH.mkdir(parents=True)


class PlistData:
    def __init__(self, raw_data) -> None:
        self.title = raw_data["playlistTitle"]
        self.keys = [song["key"] for song in raw_data["songs"]]
        self.image = raw_data["image"]


session = requests.Session()


def download_song(url: str, save_path: Path = SAVE_PATH):
    r = session.get(url, stream=True)
    name = r.headers["content-disposition"].split("filename=")[1]
    name = name.strip("\"'")

    save_path.mkdir(parents=True, exist_ok=True)
    filename = save_path / name
    assert save_path in filename.parents
    name_wo_ext = filename.with_suffix("")

    chunk_size = 8192
    with open(filename, "wb") as f:
        for chunk in r.iter_content(chunk_size):
            f.write(chunk)

    with zipfile.ZipFile(filename, "r") as zip:
        for f in zip.infolist():
            zip.extract(f, path=name_wo_ext)

    filename.unlink()


def process_plist(raw_json: str):
    json_obj = json.loads(raw_json)
    plist_data = PlistData(json_obj)
    plist_save_path = SAVE_PATH / plist_data.title

    bar = tqdm(
        total=len(plist_data.keys), desc=f"Downloading playlist [{plist_data.title}]"
    )
    for batch in batched(plist_data.keys, n=BATCH_SIZE_MAX):
        r = session.get(f"{API_ENDPOINT}/maps/ids/{','.join(batch)}")
        r.raise_for_status()
        song_details = r.json()
        for song in song_details.values():
            url = song["versions"][0]["downloadURL"]
            download_song(url, plist_save_path)
            tqdm.write(f"Done downloading song [{song.get('name')}]")
            bar.update()

    bar.close()


if __name__ == "__main__":
    files = [Path(f) for f in argv[1:]]
    for f in tqdm(files, desc="Total process"):
        assert f.exists(), f"文件不存在：{f}"
        process_plist(f.read_text())
