import os
import requests
import sys

# Zenodo record ID and file key
RECORD_ID = "13131875"
FILE_KEY = "sb-pretrained.ckpt"
DOWNLOAD_URL = f"https://zenodo.org/api/records/{RECORD_ID}/files/{FILE_KEY}/content"

# Default cache directory (user-local, not inside the repo)
DEFAULT_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "react-ot", "checkpoints")


def get_checkpoint_path(custom_path: str = None) -> str:
    """Return the path to the checkpoint, using custom_path or the default cache location."""
    if custom_path:
        return custom_path
    return os.path.join(DEFAULT_CACHE_DIR, FILE_KEY)


def download_file(url: str, dest_path: str) -> None:
    """Download a file from a URL with progress reporting."""
    print(f"Downloading {url} to {dest_path}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get("content-length", 0))

    with open(dest_path, "wb") as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = 100 * downloaded / total_size
                    sys.stdout.write(f"\rProgress: {percent:.1f}%")
                    sys.stdout.flush()
    print("\nDownload complete.")


def main() -> None:
    """Download the React-OT checkpoint to ~/.cache/react-ot/checkpoints/."""
    dest_path = get_checkpoint_path()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if os.path.exists(dest_path):
        print(f"Checkpoint already exists at {dest_path}")
    else:
        download_file(DOWNLOAD_URL, dest_path)


if __name__ == "__main__":
    main()
