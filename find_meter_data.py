r"""

Instructions on how to run (same as README.md):

- move this script and track_date.csv to the Downloads folder on the computer that has the harvest data on it
- find the Downloads folder with the script
    - go to file explorer and click on the Downloads folder
    - click on the address bar and copy the path (e.g. C:\Users\[Username]\Downloads)
- go to search bar at the bottom and type powershell and click on Windows Powershell
- paste in the copied file address and hit enter:
    cd "C:\Users\[Username]\Downloads"
- take the previous address, remove Downloads and paste it at the end of the command below and hit enter:
    python3 find_meter_data.py C:/Users/[Username]/
- then open file explorer and go to the Documents folder and you should see a NewData folder 
  with the copied files that you should then move the usb drive stick

""" 

r""" (same as README.md)
Find the MeterDataTest folder in the harvest computer's Documents folder.

Usage:
    python find_meter_data.py C:/Users/[Username]/   # all user profiles on a local machine

The script looks in each user's Documents folder (including the OneDrive-redirected
Documents folder) and searches up to --depth levels below it for MeterDataTest.

Inside MeterDataTest it looks through each subfolder and copies the CSV files
(named YYYY-MM-DD_<meter>.csv) dated on or after the date in track_date.csv into
a NewData folder in the same Documents folder, keeping the meter subfolders.
Files already in NewData that are unchanged (same size and modified time) are skipped;
a file that has grown since the last run is copied again. After a run with no copy
failures, a new row is added at the top of track_date.csv (under the header
"Most Recent, Date Pulled") with the newest file date copied and today's date; older rows
are kept. The next run starts from the top row's Most Recent date. Use --dest to copy elsewhere.
"""
import argparse
import csv
import datetime
import os
import shutil
import sys

TARGET = "MeterDataTest"
NEW_DATA_DIR = "NewData"
DEFAULT_TRACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track_date.csv")

r"""Return the 'Users' directory for a drive root or network machine name."""
def find_users_dir(root):
    root = root.rstrip("\\/")
    candidates = []
    if root.startswith("\\\\") and root.count("\\") == 2:
        # bare \\PCNAME -> use the admin share
        candidates.append(os.path.join(root, "C$", "Users"))
    candidates += [
        os.path.join(root, "Users"),
        root,
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


r"""Yield every Documents folder under the given Users dir (or a single profile)."""
def documents_folders(users_dir):
    # If the path is itself a profile, treat it as the only user.
    if os.path.basename(users_dir).lower() != "users" and os.path.isdir(os.path.join(users_dir, "Documents")):
        profiles = [users_dir]
    else:
        try:
            profiles = [e.path for e in os.scandir(users_dir) if e.is_dir()]
        except OSError as e:
            print(f"Cannot read {users_dir}: {e}", file=sys.stderr)
            return
    for profile in profiles:
        for sub in ("Documents", os.path.join("OneDrive", "Documents"),
                    os.path.join("OneDrive - University of Hawaii", "Documents")):
            path = os.path.join(profile, sub)
            if os.path.isdir(path):
                yield path
        # Any other OneDrive* variant (e.g. "OneDrive - <org>")
        try:
            for e in os.scandir(profile):
                if e.is_dir() and e.name.lower().startswith("onedrive"):
                    path = os.path.join(e.path, "Documents")
                    if os.path.isdir(path):
                        yield path
        except OSError:
            pass


r"""Yield paths named MeterDataTest within `depth` levels below `folder`."""
def search(folder, depth):
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return  # permission denied, etc.
    for e in entries:
        try:
            if not e.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        if e.name.lower() == TARGET.lower():
            yield e.path
        elif depth > 1:
            yield from search(e.path, depth - 1)


r"""Return the date stored in track_date.csv (first YYYY-MM-DD value after the header)."""
def read_track_date(path):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except OSError as e:
        sys.exit(f"Cannot read {path}: {e}")
    for row in rows[1:]:
        if row:
            try:
                return datetime.date.fromisoformat(row[0].strip())
            except ValueError:
                continue
    sys.exit(f"No YYYY-MM-DD date found in {path}")


r"""Add a new top row (newest data date, today's pull date) under the header, keeping older rows."""
def write_track_date(path, date):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            old = [r for r in csv.reader(f, skipinitialspace=True)][1:]
    except OSError:
        old = []
    rows = [[date.isoformat(), datetime.date.today().isoformat()]] + [r for r in old if r]
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("Most Recent, Date Pulled\n")
            for r in rows:
                f.write(", ".join(c.strip() for c in r) + "\n")
    except OSError as e:
        sys.exit(f"Cannot write {path}: {e}")


r"""
Return CSV files in each subfolder of meter_dir whose filename date is >= since.

Files are expected to be named YYYY-MM-DD_<meter>.csv.
"""
def csv_files_since(meter_dir, since):
    hits = []
    try:
        subfolders = [e.path for e in os.scandir(meter_dir) if e.is_dir()]
    except OSError:
        return hits
    for sub in sorted(subfolders):
        try:
            names = sorted(os.listdir(sub))
        except OSError:
            continue
        for name in names:
            if not name.lower().endswith(".csv"):
                continue
            try:
                file_date = datetime.date.fromisoformat(name[:10])
            except ValueError:
                continue  # no date prefix
            if file_date >= since:
                hits.append(os.path.join(sub, name))
    return hits


r"""Copy files into dest_root, keeping each meter subfolder. Returns (copied, skipped, failed)."""
def copy_files(files, meter_dir, dest_root):
    copied = skipped = failed = 0
    for src in files:
        dst = os.path.join(dest_root, os.path.relpath(src, meter_dir))
        try:
            # Minute data: a file can grow during the day, so only skip an
            # identical copy (same size and modified time, which copy2 preserves).
            if os.path.isfile(dst):
                s, d = os.stat(src), os.stat(dst)
                if s.st_size == d.st_size and int(s.st_mtime) == int(d.st_mtime):
                    skipped += 1
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        except OSError as e:
            print(f"    Could not copy {src}: {e}", file=sys.stderr)
            failed += 1
    return copied, skipped, failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help=r"\\PCNAME, a drive like D:\, or a path to a Users folder / user profile")
    ap.add_argument("--depth", type=int, default=4, help="how many levels below Documents to search (default 4)")
    ap.add_argument("--track-file", default=DEFAULT_TRACK_FILE,
                    help="CSV holding the start date (default: track_date.csv next to this script)")
    ap.add_argument("--dest", default=None,
                    help=f"folder to copy files into (default: {NEW_DATA_DIR} inside the Documents folder "
                         f"where {TARGET} was found)")
    args = ap.parse_args()

    users_dir = find_users_dir(args.root)
    if not users_dir:
        sys.exit(f"Could not find a Users folder at {args.root}. "
                 "Check the computer is on, reachable, and you have admin-share access.")

    since = read_track_date(args.track_file)
    print(f"Looking for CSV files dated {since.isoformat()} or later.")

    found = []
    seen = set()
    total_copied = total_skipped = total_failed = 0
    newest = None  # newest file date seen across all matches
    for docs in documents_folders(users_dir):
        key = os.path.normcase(docs)
        if key in seen:
            continue
        seen.add(key)
        print(f"Searching {docs} ...")
        for hit in search(docs, args.depth):
            print(f"  FOUND: {hit}")
            found.append(hit)
            files = csv_files_since(hit, since)
            for f in files:
                d = datetime.date.fromisoformat(os.path.basename(f)[:10])
                if newest is None or d > newest:
                    newest = d
            dest_root = args.dest or os.path.join(docs, NEW_DATA_DIR)
            copied, skipped, failed = copy_files(files, hit, dest_root)
            total_copied += copied
            total_skipped += skipped
            total_failed += failed
            print(f"    {len(files)} file(s) since {since.isoformat()}: "
                  f"{copied} copied, {skipped} already present, {failed} failed -> {dest_root}")

    if not found:
        print(f"No {TARGET} folder found.")
        sys.exit(1)
    print(f"\n{len(found)} match(es): {total_copied} file(s) copied, "
          f"{total_skipped} already present, {total_failed} failed.")

    if total_failed:
        print(f"Some files failed to copy, so {args.track_file} was left at {since.isoformat()}.")
        sys.exit(1)
    if newest is None:
        write_track_date(args.track_file, since)
        print(f"No files dated {since.isoformat()} or later; refreshed pull date in {args.track_file}.")
    else:
        write_track_date(args.track_file, newest)
        print(f"Updated {args.track_file}: {since.isoformat()} -> {newest.isoformat()}")


if __name__ == "__main__":
    main()
