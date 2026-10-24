"""Download and unpack the iMAKS dataset (Zenodo 20075430) into data/raw/imaks/."""
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://zenodo.org/records/20075430/files/iMAKS_dataset.zip?download=1"


def download(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    if (raw_dir / "kg_seed").exists():
        return
    data = urllib.request.urlopen(URL).read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(raw_dir)


if __name__ == "__main__":
    download(Path("data/raw/imaks"))
