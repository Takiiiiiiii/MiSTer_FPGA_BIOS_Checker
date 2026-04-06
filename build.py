#!/usr/bin/env python3
"""
build.py — MiSTerFPGA-BIOS data pipeline.

Fetches the live ajgowans/BiosDB_MiSTer database, merges hand-curated extras
and known gap systems, then emits four artifacts:

  docs/data/bios.json    — normalized catalog consumed by the web app
  docs/data/meta.json    — build provenance (upstream timestamp, counts)
  BIOS_LIST.md           — human-browsable markdown table
  scripts/check_bios.sh  — MiSTer-runnable shell scanner with embedded hashes

Zero non-stdlib dependencies. Run manually or via GitHub Actions.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BIOSDB_URL = "https://raw.githubusercontent.com/ajgowans/BiosDB_MiSTer/db/bios_db.json.zip"
RETROBIOS_DB_URL = "https://raw.githubusercontent.com/Abdess/retrobios/main/database.json"
RETROBIOS_RAW_BASE = "https://raw.githubusercontent.com/Abdess/retrobios/main/"
REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
DOCS_DATA_DIR = REPO_ROOT / "docs" / "data"
SCRIPTS_DIR = REPO_ROOT / "scripts"


def fetch_biosdb() -> dict:
    """Download and extract the live BiosDB JSON from GitHub."""
    print(f"fetching {BIOSDB_URL}")
    req = urllib.request.Request(BIOSDB_URL, headers={"User-Agent": "MiSTerFPGA-BIOS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        zip_bytes = resp.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if "bios_db.json" not in names:
            raise RuntimeError(f"unexpected zip contents: {names}")
        with zf.open("bios_db.json") as f:
            return json.load(f)


def fetch_retrobios() -> dict:
    """Download retrobios database.json. Returns empty dict if unreachable."""
    print(f"fetching {RETROBIOS_DB_URL}")
    try:
        req = urllib.request.Request(RETROBIOS_DB_URL, headers={"User-Agent": "MiSTerFPGA-BIOS/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"  warning: retrobios fetch failed ({e}) — continuing without it", file=sys.stderr)
        return {}


def build_retrobios_lookup(rb_db: dict) -> dict:
    """Return {md5: retrobios_path} using shortest path as canonical on collision."""
    lookup: dict[str, str] = {}
    for _sha1, info in rb_db.get("files", {}).items():
        md5 = info.get("md5")
        path = info.get("path")
        if not md5 or not path:
            continue
        existing = lookup.get(md5)
        if existing is None or len(path) < len(existing):
            lookup[md5] = path
    return lookup


def retrobios_url_for(path: str) -> str:
    """Build a raw GitHub URL from a retrobios repo-relative path."""
    from urllib.parse import quote
    return RETROBIOS_RAW_BASE + quote(path)


def normalize_biosdb(db: dict) -> list[dict]:
    """Flatten BiosDB files + zips into a uniform entry list."""
    tag_by_id = {tag_id: name for name, tag_id in db.get("tag_dictionary", {}).items()}
    entries: list[dict] = []

    for raw_path, info in db.get("files", {}).items():
        entries.append(_normalize_entry(raw_path, info, tag_by_id, source="biosdb"))

    for zip_id, zip_info in db.get("zips", {}).items():
        summary = zip_info.get("internal_summary", {})
        for raw_path, info in summary.get("files", {}).items():
            entry = _normalize_entry(raw_path, info, tag_by_id, source="biosdb-zip")
            entry["notes"] = zip_info.get("description", entry.get("notes", ""))
            entry["url"] = zip_info.get("contents_file", {}).get("url", entry.get("url"))
            entries.append(entry)

    return entries


def _normalize_entry(raw_path: str, info: dict, tag_by_id: dict[int, str], source: str) -> dict:
    # BiosDB paths look like "|games/N64/boot.rom" — strip leading '|'
    path = raw_path.lstrip("|").lstrip("/")
    parts = path.split("/")
    core = parts[1] if len(parts) >= 3 and parts[0] == "games" else parts[0]
    filename = parts[-1]
    tags = [tag_by_id.get(t, str(t)) for t in info.get("tags", [])]
    # drop structural tags that add no value
    tags = [t for t in tags if t not in ("games", "bios", "extrautilities", "mglbios")]
    return {
        "core": core,
        "filename": filename,
        "target_path": path,
        "size": info.get("size"),
        "md5": info.get("hash"),
        "url": info.get("url"),
        "tags": tags,
        "source": source,
        "notes": "",
        "status": "catalog",
    }


def load_extras() -> list[dict]:
    """Load hand-curated BIOS entries from data/extras.json."""
    path = DATA_DIR / "extras.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    entries: list[dict] = []
    for e in raw.get("entries", []):
        entries.append({
            "core": e["core"],
            "filename": e["filename"],
            "target_path": f"games/{e['core']}/{e['filename']}",
            "size": e.get("size"),
            "md5": e.get("md5"),
            "url": None,
            "tags": ([] if e.get("required", True) else ["optional"]) + [f"src:{e.get('md5_source', 'unknown')}"],
            "source": "extras",
            "notes": e.get("notes", ""),
            "status": "catalog",
        })
    return entries


def load_gaps() -> list[dict]:
    """Load gap-system entries from data/gap_systems.json."""
    path = DATA_DIR / "gap_systems.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    entries: list[dict] = []
    for e in raw.get("entries", []):
        entries.append({
            "core": e["core"],
            "filename": e["filename"],
            "target_path": f"games/{e['core']}/{e['filename']}",
            "size": e.get("size_hint"),
            "md5": None,
            "url": None,
            "tags": ["gap"] + (["research"] if e.get("research_urls") else []),
            "source": "gap",
            "notes": e.get("notes", ""),
            "research_urls": e.get("research_urls", []),
            "status": "gap",
        })
    return entries


def load_recipes() -> list[dict]:
    """Load recipe entries from data/recipes.json."""
    path = DATA_DIR / "recipes.json"
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    entries: list[dict] = []
    for e in raw.get("entries", []):
        entries.append({
            "core": e["core"],
            "filename": e["filename"],
            "target_path": e.get("target_path", f"games/{e['core']}/{e['filename']}"),
            "size": e.get("size"),
            "md5": e["variants"][0]["md5"] if e.get("variants") else None,
            "url": None,
            "tags": ["recipe"],
            "source": "recipe",
            "notes": e.get("notes", ""),
            "status": "recipe",
            "recipe": {
                "variants": e["variants"],
            },
        })
    return entries


def dedupe(entries: list[dict]) -> list[dict]:
    """Deduplicate by target_path, preferring biosdb > extras > recipe > gap."""
    priority = {"biosdb": 0, "biosdb-zip": 1, "extras": 2, "recipe": 3, "gap": 4}
    seen: dict[str, dict] = {}
    for e in entries:
        key = e["target_path"]
        if key not in seen or priority.get(e["source"], 5) < priority.get(seen[key]["source"], 5):
            seen[key] = e
    return sorted(seen.values(), key=lambda e: (e["core"].lower(), e["filename"].lower()))


def enrich_with_retrobios(entries: list[dict], rb_lookup: dict, rb_db: dict) -> None:
    """Attach retrobios_url and retrobios_name to entries where MD5 matches. Mutates in place."""
    matched = 0
    for e in entries:
        md5 = e.get("md5")
        if not md5:
            continue
        path = rb_lookup.get(md5)
        if not path:
            continue
        e["retrobios_url"] = retrobios_url_for(path)
        e["retrobios_name"] = path.rsplit("/", 1)[-1]
        matched += 1
    total_hashable = sum(1 for e in entries if e.get("md5"))
    print(f"  retrobios matched {matched}/{total_hashable} entries by MD5")


def build_meta(db: dict, entries: list[dict], rb_db: dict) -> dict:
    upstream_ts = db.get("timestamp")
    upstream_iso = (
        datetime.fromtimestamp(upstream_ts, tz=timezone.utc).isoformat()
        if upstream_ts else None
    )
    by_source: dict[str, int] = {}
    cores: set[str] = set()
    retrobios_matched = 0
    for e in entries:
        by_source[e["source"]] = by_source.get(e["source"], 0) + 1
        cores.add(e["core"])
        if e.get("retrobios_url"):
            retrobios_matched += 1
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "upstream_source": BIOSDB_URL,
        "upstream_timestamp": upstream_ts,
        "upstream_iso": upstream_iso,
        "retrobios_source": RETROBIOS_DB_URL,
        "retrobios_generated_at": rb_db.get("generated_at"),
        "retrobios_total_files": rb_db.get("total_files"),
        "counts": {
            "total": len(entries),
            "by_source": by_source,
            "cores": len(cores),
            "retrobios_matched": retrobios_matched,
        },
    }


def write_bios_json(entries: list[dict], meta: dict) -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA_DIR / "bios.json").write_text(
        json.dumps({"entries": entries}, indent=2) + "\n"
    )
    (DOCS_DATA_DIR / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")


def write_markdown(entries: list[dict], meta: dict) -> None:
    """Emit BIOS_LIST.md grouped by core."""
    upstream = meta.get("upstream_iso") or "unknown"
    counts = meta["counts"]
    by_src = counts["by_source"]
    lines: list[str] = [
        "# MiSTer FPGA BIOS List",
        "",
        f"_Generated {meta['generated'][:10]} from [ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer) @ {upstream[:10] if upstream != 'unknown' else 'unknown'}_",
        "",
        "## Summary",
        "",
        f"- **{counts['total']}** total entries across **{counts['cores']}** cores",
        f"- {by_src.get('biosdb', 0) + by_src.get('biosdb-zip', 0)} from BiosDB upstream",
        *([ f"- {by_src['extras']} from hand-curated [extras.json](data/extras.json)"] if by_src.get('extras') else []),
        f"- {by_src.get('gap', 0)} flagged gap entries (needs community-verified hash)",
        f"- {counts.get('retrobios_matched', 0)} entries have a mirror in [retrobios](https://github.com/Abdess/retrobios) (2nd download source)",
        "",
        "## How to use",
        "",
        "1. Each BIOS belongs at the **Target** path on your MiSTer SD card (relative to `/media/fat/`).",
        "2. If you're missing a file, **copy its MD5 hash and paste into Google** — this is usually the fastest way to find a legitimate copy.",
        "3. For an interactive experience that scans your SD card, use the [web app](https://takiiiiiii.github.io/MiSTerFPGA-BIOS/).",
        "",
        "---",
        "",
        "## BIOS by System",
        "",
    ]

    by_core: dict[str, list[dict]] = {}
    for e in entries:
        by_core.setdefault(e["core"], []).append(e)

    for core in sorted(by_core.keys(), key=str.lower):
        core_entries = by_core[core]
        lines.append(f"### {core}")
        lines.append("")
        lines.append(f"Target directory: `/media/fat/games/{core}/`")
        lines.append("")
        lines.append("| File | Size | MD5 | Notes |")
        lines.append("|---|---:|---|---|")
        for e in core_entries:
            size = f"{e['size']:,}" if e.get("size") else "?"
            md5 = f"`{e['md5']}`" if e.get("md5") else "_gap — no verified hash_"
            notes_parts: list[str] = []
            if e.get("notes"):
                notes_parts.append(e["notes"])
            if e["source"] == "extras":
                notes_parts.append("_(extras.json)_")
            elif e["source"] == "gap":
                notes_parts.append("_(gap — contribute hash via PR)_")
            if e.get("url"):
                notes_parts.append(f"[archive.org]({e['url']})")
            if e.get("retrobios_url"):
                notes_parts.append(f"[retrobios]({e['retrobios_url']})")
            if e.get("recipe"):
                variant_names = [v["name"] for v in e["recipe"]["variants"]]
                vlist = ", ".join(variant_names)
                notes_parts.append(f"_Assembled via recipe. Variants: {vlist}_")
            notes = "<br>".join(notes_parts) or "—"
            lines.append(f"| `{e['filename']}` | {size} | {md5} | {notes} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Data sources")
    lines.append("")
    lines.append("- [ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer) — the live community BIOS database used by MiSTer Downloader / Update_All_MiSTer.")
    lines.append("- [Abdess/retrobios](https://github.com/Abdess/retrobios) — 7,302-file multi-emulator BIOS database cross-referenced by MD5 as a second download source when archive.org is down.")
    lines.append("- `data/recipes.json` — BIOS files that need to be assembled from components.")
    lines.append("")

    (REPO_ROOT / "BIOS_LIST.md").write_text("\n".join(lines))


def write_check_script(entries: list[dict], meta: dict) -> None:
    """Emit scripts/check_bios.sh — POSIX shell scanner with embedded hashes."""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    hash_entries = [e for e in entries if e.get("md5") and e.get("size") is not None]

    lines: list[str] = [
        "#!/bin/sh",
        "# check_bios.sh - MiSTer BIOS scanner",
        f"# {meta['counts']['total']} BIOS entries, last updated {meta['generated'][:10]}",
        "#",
        "# Checks your MiSTer SD card for missing or mismatched BIOS files",
        "# and writes a report to /media/fat/bios_report.txt.",
        "#",
        "# Install:",
        "#   wget -O /media/fat/Scripts/check_bios.sh \\",
        "#     https://raw.githubusercontent.com/Takiiiiiii/MiSTerFPGA-BIOS/main/scripts/check_bios.sh",
        "#   sh /media/fat/Scripts/check_bios.sh",
        "",
        'GAMES_DIR="${GAMES_DIR:-/media/fat/games}"',
        'REPORT="${REPORT:-/media/fat/bios_report.txt}"',
        "",
        '# Format: "<core>|<filename>|<target_path_relative_to_games>|<size>|<md5>"',
        "ENTRIES=\"",
    ]

    for e in hash_entries:
        # strip leading "games/" from target_path to get path relative to GAMES_DIR
        rel = e["target_path"]
        if rel.startswith("games/"):
            rel = rel[len("games/"):]
        # escape pipes in filenames (shouldn't happen, but safe)
        safe_filename = e["filename"].replace("|", "\\|")
        lines.append(f'{e["core"]}|{safe_filename}|{rel}|{e["size"]}|{e["md5"]}')

    lines.append('"')
    lines.append("")
    lines.append(r"""
# Runtime

if ! command -v md5sum >/dev/null 2>&1; then
    echo "error: md5sum not found" >&2
    exit 1
fi

present_list=""
missing_list=""
wrong_list=""

IFS_BAK=$IFS
IFS='
'
for line in $ENTRIES; do
    [ -z "$line" ] && continue
    core=$(echo "$line" | cut -d'|' -f1)
    filename=$(echo "$line" | cut -d'|' -f2)
    rel=$(echo "$line" | cut -d'|' -f3)
    expected_size=$(echo "$line" | cut -d'|' -f4)
    expected_md5=$(echo "$line" | cut -d'|' -f5)
    full_path="$GAMES_DIR/$rel"

    if [ ! -f "$full_path" ]; then
        missing_list="$missing_list$core|$filename|$rel|$expected_size|$expected_md5
"
        continue
    fi

    actual_md5=$(md5sum "$full_path" 2>/dev/null | cut -d' ' -f1)
    if [ "$actual_md5" = "$expected_md5" ]; then
        present_list="$present_list$core|$filename
"
    else
        wrong_list="$wrong_list$core|$filename|$rel|$expected_md5|$actual_md5
"
    fi
done
IFS=$IFS_BAK

# Write report

{
    echo "MiSTer BIOS Scan Report"
    echo "======================="
    echo "Scanned: $GAMES_DIR"
    echo "Date:    $(date)"
    echo ""

    present_count=$(printf "%s" "$present_list" | awk 'NF>0{c++} END{print c+0}')
    missing_count=$(printf "%s" "$missing_list" | awk 'NF>0{c++} END{print c+0}')
    wrong_count=$(printf "%s" "$wrong_list" | awk 'NF>0{c++} END{print c+0}')

    echo "SUMMARY"
    echo "-------"
    echo "  Present & correct: $present_count"
    echo "  Missing:           $missing_count"
    echo "  Wrong hash:        $wrong_count"
    echo ""

    if [ "$missing_count" -gt 0 ]; then
        echo "MISSING FILES (google the MD5 hash to find copies)"
        echo "---------------------------------------------------"
        IFS='
'
        for line in $missing_list; do
            [ -z "$line" ] && continue
            core=$(echo "$line" | cut -d'|' -f1)
            filename=$(echo "$line" | cut -d'|' -f2)
            rel=$(echo "$line" | cut -d'|' -f3)
            size=$(echo "$line" | cut -d'|' -f4)
            md5=$(echo "$line" | cut -d'|' -f5)
            echo "  [$core] $filename"
            echo "    path: games/$rel"
            echo "    size: $size bytes"
            echo "    md5:  $md5"
            echo ""
        done
        IFS=$IFS_BAK
    fi

    if [ "$wrong_count" -gt 0 ]; then
        echo "WRONG HASH (file present but does not match expected MD5)"
        echo "----------------------------------------------------------"
        IFS='
'
        for line in $wrong_list; do
            [ -z "$line" ] && continue
            core=$(echo "$line" | cut -d'|' -f1)
            filename=$(echo "$line" | cut -d'|' -f2)
            rel=$(echo "$line" | cut -d'|' -f3)
            expected=$(echo "$line" | cut -d'|' -f4)
            actual=$(echo "$line" | cut -d'|' -f5)
            echo "  [$core] $filename (games/$rel)"
            echo "    expected: $expected"
            echo "    actual:   $actual"
            echo ""
        done
        IFS=$IFS_BAK
    fi

    echo ""
    echo "For the interactive checker, visit:"
    echo "  https://takiiiiiii.github.io/MiSTerFPGA-BIOS/"
} > "$REPORT"

# Print results to terminal
echo ""
if [ "$missing_count" -eq 0 ] && [ "$wrong_count" -eq 0 ]; then
    echo "All $present_count BIOS files present and verified."
else
    if [ "$missing_count" -gt 0 ]; then
        echo "MISSING:"
        IFS='
'
        for line in $missing_list; do
            [ -z "$line" ] && continue
            core=$(echo "$line" | cut -d'|' -f1)
            filename=$(echo "$line" | cut -d'|' -f2)
            printf "  %-18s %s\n" "[$core]" "$filename"
        done
        IFS=$IFS_BAK
    fi
    if [ "$wrong_count" -gt 0 ]; then
        echo "WRONG HASH:"
        IFS='
'
        for line in $wrong_list; do
            [ -z "$line" ] && continue
            core=$(echo "$line" | cut -d'|' -f1)
            filename=$(echo "$line" | cut -d'|' -f2)
            printf "  %-18s %s\n" "[$core]" "$filename"
        done
        IFS=$IFS_BAK
    fi
    echo ""
    echo "$present_count ok / $missing_count missing / $wrong_count wrong"
fi
echo "Full report: $REPORT"
""")

    script_path = SCRIPTS_DIR / "check_bios.sh"
    script_path.write_text("\n".join(lines))
    script_path.chmod(0o755)


def main() -> int:
    try:
        db = fetch_biosdb()
    except Exception as e:
        print(f"error fetching BiosDB: {e}", file=sys.stderr)
        return 1

    biosdb_entries = normalize_biosdb(db)
    extras = load_extras()
    gaps = load_gaps()
    recipes = load_recipes()

    all_entries = dedupe(biosdb_entries + extras + gaps + recipes)

    rb_db = fetch_retrobios()
    rb_lookup = build_retrobios_lookup(rb_db)
    enrich_with_retrobios(all_entries, rb_lookup, rb_db)

    meta = build_meta(db, all_entries, rb_db)

    write_bios_json(all_entries, meta)
    write_markdown(all_entries, meta)
    write_check_script(all_entries, meta)

    print(f"built {meta['counts']['total']} entries across {meta['counts']['cores']} cores")
    print(f"  by source: {meta['counts']['by_source']}")
    print(f"  retrobios coverage: {meta['counts']['retrobios_matched']} entries with 2nd source")
    print("  outputs:")
    print(f"    {DOCS_DATA_DIR / 'bios.json'}")
    print(f"    {DOCS_DATA_DIR / 'meta.json'}")
    print(f"    {REPO_ROOT / 'BIOS_LIST.md'}")
    print(f"    {SCRIPTS_DIR / 'check_bios.sh'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
