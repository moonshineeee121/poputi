"""Download project-local Windows PostgreSQL and illustrative Unsplash photographs."""
import argparse
import concurrent.futures
import os
import hashlib
import shutil
import tempfile
from pathlib import Path
import subprocess
import urllib.request
import zipfile
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
TOOLS = ROOT / ".tools"
SOURCE_BIN = TOOLS / "postgres" / "pgsql" / "bin"
# PostgreSQL's Windows tools can fail on non-ASCII installation/data paths.
# The source project stays in place; only the local database runtime uses Temp.
DEFAULT_RUNTIME = Path(tempfile.gettempdir()) / ("poputi-" + hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]) if os.name == "nt" and not str(ROOT).isascii() else ROOT / ".runtime"
RUNTIME = Path(os.getenv("POPUTI_RUNTIME_DIR", str(DEFAULT_RUNTIME))).expanduser().resolve()
DATA = RUNTIME / "data"
BIN = RUNTIME / "postgres" / "pgsql" / "bin"
PHOTOS = {
    "hero": "photo-1464822759023-fed622ff2c3b",
    "altai": "photo-1506905925346-21bda4d32df4",
    "dagestan": "photo-1454496522488-7a8e488e8606",
    "karelia": "photo-1441974231531-c6227db76b6e",
    "baikal": "photo-1501785888041-af3ef285b470",
    "kamchatka": "photo-1519681393784-d120267933ba",
    "georgia": "photo-1472396961693-142e6e269027",
}


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1000:
        return
    request = urllib.request.Request(url, headers={"User-Agent": "Poputi-local-development/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    print(f"Downloaded {path.name}", flush=True)


def photo(item):
    name, photo_id = item
    width = 2200 if name == "hero" else 1000
    download(f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w={width}&q=85", ROOT / "static" / "img" / f"{name}.jpg")


def postgres():
    if (SOURCE_BIN / "initdb.exe").exists():
        return
    archive = TOOLS / "downloads" / "postgres.zip"
    download("https://get.enterprisedb.com/postgresql/postgresql-17.11-1-windows-x64-binaries.zip", archive)
    destination = TOOLS / "postgres"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if name.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                target = (destination / name).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise RuntimeError("Invalid archive path")
                bundle.extract(name, destination)
    print("PostgreSQL binaries ready", flush=True)


def start():
    if os.name != "nt":
        raise SystemExit("Use docker compose up -d db on this platform.")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not (BIN / "initdb.exe").exists():
        shutil.copytree(TOOLS / "postgres", RUNTIME / "postgres", dirs_exist_ok=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if not (DATA / "PG_VERSION").exists():
        password_file = RUNTIME / "init-password"
        password_file.write_text("poputi_dev\n", encoding="utf-8")
        try:
            subprocess.run([str(BIN / "initdb.exe"), "-D", str(DATA), "-U", "poputi", "--encoding=UTF8", "--locale=C", "--auth=scram-sha-256", f"--pwfile={password_file}"], check=True)
        finally:
            password_file.unlink(missing_ok=True)
    status = subprocess.run([str(BIN / "pg_ctl.exe"), "-D", str(DATA), "status"], capture_output=True)
    if status.returncode:
        subprocess.run([str(BIN / "pg_ctl.exe"), "-D", str(DATA), "-l", str(RUNTIME / "postgres.log"), "-o", "-h 127.0.0.1 -p 54329", "-w", "start"], check=True)
    env = dict(os.environ, PGPASSWORD="poputi_dev")
    exists = subprocess.run([str(BIN / "psql.exe"), "-h", "127.0.0.1", "-p", "54329", "-U", "poputi", "-d", "postgres", "-tAc", "SELECT 1 FROM pg_database WHERE datname='poputi'"], env=env, capture_output=True, text=True, check=True)
    if "1" not in exists.stdout:
        subprocess.run([str(BIN / "createdb.exe"), "-h", "127.0.0.1", "-p", "54329", "-U", "poputi", "poputi"], env=env, check=True)
    print("PostgreSQL available at 127.0.0.1:54329", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["download", "start", "stop"])
    action = parser.parse_args().action
    if action == "download":
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            jobs = [pool.submit(photo, item) for item in PHOTOS.items()]
            jobs.append(pool.submit(postgres))
            for job in jobs:
                job.result()
    elif action == "start":
        start()
    elif (DATA / "postmaster.pid").exists():
        subprocess.run([str(BIN / "pg_ctl.exe"), "-D", str(DATA), "-w", "stop"], check=True)
