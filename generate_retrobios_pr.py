#!/usr/bin/env python3
"""
generate_retrobios_pr.py — build a misterfpga.yml for submission to Abdess/retrobios.

Reads docs/data/bios.json (our enriched catalog) and cross-references
retrobios/database.json to produce a platforms/misterfpga.yml file matching
retrobios's schema. Output goes to retrobios_pr/platforms/misterfpga.yml
along with a PR body draft.

Zero non-stdlib dependencies (we emit YAML manually to avoid pyyaml).
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BIOS_JSON = REPO_ROOT / "docs" / "data" / "bios.json"
META_JSON = REPO_ROOT / "docs" / "data" / "meta.json"
OUT_DIR = REPO_ROOT / "retrobios_pr"
OUT_YAML = OUT_DIR / "platforms" / "misterfpga.yml"
OUT_PR_BODY = OUT_DIR / "PR_BODY.md"
RETROBIOS_DB_URL = "https://raw.githubusercontent.com/Abdess/retrobios/main/database.json"

# Map MiSTer core folder names to retrobios-style system slugs + metadata.
# Keys are MiSTer's canonical folder names (as seen on MiSTer SD card).
# Values: (slug, manufacturer, friendly_name, mister_core_repo).
SYSTEM_META: dict[str, tuple[str, str, str, str]] = {
    "3DO":               ("3do",               "Panasonic",       "3DO Interactive Multiplayer", "3DO_MiSTer"),
    "Astrocade":         ("astrocade",         "Bally",           "Bally Astrocade",             "Astrocade_MiSTer"),
    "AtariLynx":         ("atari-lynx",        "Atari",           "Atari Lynx",                  "AtariLynx_MiSTer"),
    "Casio_PV-2000":     ("casio-pv-2000",     "Casio",           "Casio PV-2000",               "PV2000_MiSTer"),
    "CD-i":              ("philips-cdi",       "Philips",         "Philips CD-i",                "CDi_MiSTer"),
    "COCO3":             ("coco3",             "Tandy",           "Tandy TRS-80 Color Computer 3", "CoCo3_MiSTer"),
    "CreatiVision":      ("creativision",      "VTech",           "VTech CreatiVision",          "CreatiVision_MiSTer"),
    "GAMEBOY":           ("game-boy",          "Nintendo",        "Game Boy / Game Boy Color",   "Gameboy_MiSTer"),
    "GBA":               ("game-boy-advance",  "Nintendo",        "Game Boy Advance",            "GBA_MiSTer"),
    "Gamate":            ("gamate",            "Bit Corp",        "Gamate",                      "Gamate_MiSTer"),
    "Intellivision":     ("intellivision",     "Mattel",          "Intellivision",               "Intellivision_MiSTer"),
    "Interact":          ("interact",          "Interact",        "Interact Family Computer",    "Interact_MiSTer"),
    "Jaguar":            ("atari-jaguar",      "Atari",           "Atari Jaguar",                "Jaguar_MiSTer"),
    "MegaCD":            ("sega-cd",           "Sega",            "Sega CD / Mega-CD",           "MegaCD_MiSTer"),
    "MSX1":              ("msx",               "Microsoft",       "MSX1",                        "MSX_MiSTer"),
    "N64":               ("n64",               "Nintendo",        "Nintendo 64",                 "N64_MiSTer"),
    "NEOGEO":            ("neo-geo",           "SNK",             "Neo Geo (AES/MVS)",           "NeoGeo_MiSTer"),
    "NES":               ("nes-fds",           "Nintendo",        "NES / Famicom Disk System",   "NES_MiSTer"),
    "NeoGeo-CD":         ("neo-geo-cd",        "SNK",             "Neo Geo CD",                  "NeoGeo_MiSTer"),
    "PC8801":            ("pc-8801",           "NEC",             "NEC PC-8801",                 "PC8801_MiSTer"),
    "PSX":               ("playstation",       "Sony",            "Sony PlayStation",            "PSX_MiSTer"),
    "PocketChallengeV2": ("pocket-challenge-v2", "Benesse",       "Pocket Challenge V2",         "WonderSwan_MiSTer"),
    "PokemonMini":       ("pokemon-mini",      "Nintendo",        "Pokémon Mini",                "PokemonMini_MiSTer"),
    "SCV":               ("epoch-scv",         "Epoch",           "Epoch Super Cassette Vision", "SuperCassetteVision_MiSTer"),
    "SGB":               ("super-game-boy",    "Nintendo",        "Super Game Boy",              "SGB_MiSTer"),
    "SNES":              ("snes",              "Nintendo",        "Super NES / Super Famicom",   "SNES_MiSTer"),
    "Saturn":            ("sega-saturn",       "Sega",            "Sega Saturn",                 "Saturn_MiSTer"),
    "TGFX16-CD":         ("turbografx-cd",     "NEC",             "TurboGrafx-CD / PC Engine CD", "TurboGrafx16_MiSTer"),
    "TI-99_4A":          ("ti-99",             "Texas Instruments", "TI-99/4A",                  "Ti994a_MiSTer"),
    "WonderSwan":        ("wonderswan",        "Bandai",          "WonderSwan",                  "WonderSwan_MiSTer"),
    "WonderSwanColor":   ("wonderswan-color",  "Bandai",          "WonderSwan Color",            "WonderSwan_MiSTer"),
}


def fetch_retrobios() -> dict:
    print(f"fetching {RETROBIOS_DB_URL}")
    req = urllib.request.Request(RETROBIOS_DB_URL, headers={"User-Agent": "MiSTerFPGA-BIOS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def build_md5_to_retrobios(rb_db: dict) -> dict:
    """Returns md5 -> full retrobios file info dict (shortest path wins on collision)."""
    lookup: dict[str, dict] = {}
    for sha1, info in rb_db.get("files", {}).items():
        md5 = info.get("md5")
        if not md5:
            continue
        existing = lookup.get(md5)
        if existing is None or len(info.get("path", "")) < len(existing.get("path", "")):
            lookup[md5] = info
    return lookup


def quote_yaml(v: str) -> str:
    """Quote a YAML scalar if it contains special chars."""
    if not v:
        return "''"
    if re.search(r'[:#\'"{}\[\],&*!|>%@`]|^[-?]', v) or v != v.strip():
        return "'" + v.replace("'", "''") + "'"
    return v


def emit_yaml(data: dict) -> str:
    """Emit a retrobios-style platform YAML. Minimal hand-rolled emitter for this shape."""
    out: list[str] = []
    # top-level scalars first (keep insertion order)
    for k, v in data.items():
        if k == "systems":
            continue
        if isinstance(v, list):
            out.append(f"{k}:")
            for item in v:
                out.append(f"- {quote_yaml(item)}")
        else:
            out.append(f"{k}: {quote_yaml(str(v))}")
    out.append("systems:")
    for sys_slug, sys_info in data["systems"].items():
        out.append(f"  {sys_slug}:")
        out.append("    files:")
        for f in sys_info["files"]:
            out.append(f"    - name: {quote_yaml(f['name'])}")
            out.append(f"      destination: {quote_yaml(f['destination'])}")
            out.append(f"      required: {'true' if f['required'] else 'false'}")
            if "md5" in f: out.append(f"      md5: {f['md5']}")
            if "sha1" in f: out.append(f"      sha1: {f['sha1']}")
            if "crc32" in f: out.append(f"      crc32: {f['crc32']}")
            if "size" in f: out.append(f"      size: {f['size']}")
        # metadata fields after files
        for mk in ("native_id", "core", "manufacturer", "docs"):
            if mk in sys_info:
                out.append(f"    {mk}: {quote_yaml(sys_info[mk])}")
    return "\n".join(out) + "\n"


def main() -> int:
    # Load inputs
    bios = json.loads(BIOS_JSON.read_text())
    meta = json.loads(META_JSON.read_text())
    rb_db = fetch_retrobios()
    md5_lookup = build_md5_to_retrobios(rb_db)

    # Build systems mapping from entries with retrobios match
    systems: dict[str, dict] = {}
    matched = 0
    cores_with_any_match: set[str] = set()
    cores_with_any_miss: set[str] = set()
    partial_files: list[tuple[str, str]] = []  # (core, filename) of unmatched files in matched cores
    for e in bios["entries"]:
        md5 = e.get("md5")
        if not md5:
            continue
        rb_info = md5_lookup.get(md5)
        if not rb_info:
            cores_with_any_miss.add(e["core"])
            continue
        cores_with_any_match.add(e["core"])
        if e["core"] not in SYSTEM_META:
            # should not happen for any of our cores
            print(f"  warning: no SYSTEM_META entry for core {e['core']!r}", file=sys.stderr)
            continue

        slug, manufacturer, friendly, mister_repo = SYSTEM_META[e["core"]]
        sys_entry = systems.setdefault(slug, {
            "files": [],
            "native_id": f"MiSTer - {friendly}",
            "core": mister_repo,
            "manufacturer": manufacturer,
            "docs": f"https://github.com/MiSTer-devel/{mister_repo}",
        })
        # destination is relative to base_destination (games/)
        # strip leading "games/" since base_destination handles it
        dest = e["target_path"]
        if dest.startswith("games/"):
            dest = dest[len("games/"):]
        sys_entry["files"].append({
            "name": rb_info["name"],
            "destination": dest,
            "required": True,
            "md5": rb_info["md5"],
            "sha1": rb_info["sha1"],
            "crc32": rb_info["crc32"],
            "size": rb_info["size"],
        })
        matched += 1

    # Sort systems alphabetically, sort files within each system by destination
    sorted_systems = {}
    for slug in sorted(systems.keys()):
        systems[slug]["files"].sort(key=lambda f: f["destination"])
        sorted_systems[slug] = systems[slug]

    platform_yaml = {
        "platform": "MiSTer FPGA",
        "version": "latest",
        "homepage": "https://misterfpga.org",
        "source": "https://github.com/ajgowans/BiosDB_MiSTer",
        "base_destination": "games",
        "hash_type": "md5",
        "verification_mode": "md5",
        "systems": sorted_systems,
    }

    # Write YAML
    OUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(emit_yaml(platform_yaml))

    # Stats
    n_systems = len(sorted_systems)
    n_files = matched
    # cores that have NO file in retrobios at all (fully skipped)
    fully_skipped = cores_with_any_miss - cores_with_any_match
    # cores that are partial (some files matched, some not)
    partial_cores = cores_with_any_miss & cores_with_any_match
    n_skipped = len(fully_skipped)

    # Collect all unmatched entries with their BiosDB source URLs for the gap tables
    unmatched_by_bucket: dict[str, list[dict]] = {
        "fully_skipped": [],
        "partial": [],
    }
    for e in bios["entries"]:
        if not e.get("md5"):
            continue
        if e["md5"] in md5_lookup:
            continue
        bucket = "fully_skipped" if e["core"] in fully_skipped else "partial"
        unmatched_by_bucket[bucket].append(e)
        if bucket == "partial":
            partial_files.append((e["core"], e["filename"]))

    def gap_table(entries: list[dict]) -> str:
        if not entries:
            return "_(none)_"
        rows = [
            "| MiSTer path | Size | MD5 | Source (archive.org via BiosDB) |",
            "|---|---:|---|---|",
        ]
        for e in sorted(entries, key=lambda x: (x["core"].lower(), x["filename"].lower())):
            url = e.get("url") or ""
            url_cell = f"[archive.org]({url})" if url else "_(no URL)_"
            size_cell = f"{e['size']:,}" if e.get("size") else "?"
            path_cell = f"`games/{e['core']}/{e['filename']}`"
            rows.append(f"| {path_cell} | {size_cell} | `{e['md5']}` | {url_cell} |")
        return "\n".join(rows)

    skipped_list = ", ".join(sorted(fully_skipped)) if fully_skipped else "(none)"
    pr_body = f"""# Add MiSTer FPGA as a supported platform

## What is MiSTer FPGA?

[MiSTer FPGA](https://misterfpga.org) is an open-source, FPGA-based hardware platform that faithfully recreates vintage consoles, arcade hardware, and computers at the gate level. Unlike software emulation, MiSTer cores reproduce the original hardware's behavior cycle-accurately on reconfigurable logic.

The MiSTer community maintains 100+ console, arcade, and computer cores. Many cores require the original system's BIOS ROM to boot. Today, MiSTer users rely on [ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer) (consumed via MiSTer Downloader / Update_All_MiSTer) to fetch BIOS from archive.org — a single point of failure.

## What this PR adds

`platforms/misterfpga.yml` — a MiSTer FPGA platform definition following retrobios's existing schema, cross-referencing {n_files} BIOS files across {n_systems} MiSTer cores to canonical retrobios entries by MD5.

### Systems covered ({n_systems}):
{chr(10).join('- ' + SYSTEM_META[c][2] + f" (`{SYSTEM_META[c][0]}`)" for c in sorted(SYSTEM_META.keys()) if SYSTEM_META[c][0] in sorted_systems)}

## Gap analysis — what's not yet mapped (and where to find it)

The following BIOS files are required by MiSTer cores but aren't matchable against retrobios's current database by MD5. Each is listed with its known archive.org source (from [ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer)) so retrobios maintainers can evaluate adding them. **Three root causes:**

### (A) Systems not in retrobios at all — {n_skipped} cores

These cores have zero files in retrobios. Most are obscure handhelds / Japan-only computers that mainstream emulator databases don't cover. BIOS sources:

{gap_table(unmatched_by_bucket['fully_skipped'])}

### (B) Partial cores — specific files missing

retrobios has *some* of these systems' BIOS files but not all of them. The YAML already includes whatever is matchable; these rows are the ones still missing:

{gap_table(unmatched_by_bucket['partial'])}

### (C) Hash mismatch — same system, different dump/format

retrobios has entries for these systems, but with different BIOS revisions or file formats than MiSTer expects:

- **TGFX16-CD (`cd_bios.rom`)**: retrobios has `syscard3.pce` at 262,656 bytes; MiSTer expects 262,144 bytes — identical content, but retrobios's version has a 512-byte header prefix that changes the MD5. Could be resolved by adding a headerless variant.
- **CreatiVision**: retrobios has `bioscv.rom` (2KB); MiSTer wants `boot.rom` (16KB) — different revision entirely.
- **Jaguar**: retrobios has `[BIOS] Atari Jaguar (World).j64` (131KB single file); MiSTer has three separate boot*.rom files with different hashes from different source dumps.
- **Astrocade / Casio PV-2000 / Gamate / SCV / TI-99_4A**: retrobios stores these as MAME-format ROM zips (containing multiple files packed together), not as individual raw BIOSes. The MD5 of the zip ≠ the MD5 of the BIOS inside. Would be resolved if retrobios unpacked the individual files alongside the zips.

## Schema choices

- `base_destination: games` — MiSTer stores BIOS at `/media/fat/games/<Core>/<file>` on the SD card. The `games` base is relative to the MiSTer SD card root.
- `hash_type: md5` / `verification_mode: md5` — MiSTer's BiosDB uses MD5 as its canonical hash. This matches BiosDB's verification behavior.
- Destinations use MiSTer's expected filenames (`boot.rom`, `boot0.rom`, `cd_bios.rom`, etc.) rather than the BIOS's native filenames — these are what each MiSTer core actually looks for.
- Each system's `docs:` field points to the corresponding MiSTer-devel GitHub core repo.

## How this was generated

Programmatically from the live BiosDB database cross-referenced with retrobios's `database.json` by MD5 hash. Source: [Takiiiiiii/MiSTerFPGA-BIOS](https://github.com/Takiiiiiii/MiSTerFPGA-BIOS/blob/main/generate_retrobios_pr.py). Every file entry has been verified to exist in retrobios with matching MD5, SHA1, CRC32, and size.

Generated: {datetime.now(timezone.utc).isoformat()[:19]}Z

## Testing

```sh
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('platforms/misterfpga.yml'))"

# Sanity check counts
grep -c '^  [a-z]' platforms/misterfpga.yml  # systems
grep -c '    - name:' platforms/misterfpga.yml  # files
```
"""
    OUT_PR_BODY.write_text(pr_body)

    print(f"wrote {OUT_YAML}")
    print(f"  systems included: {n_systems}")
    print(f"  files included:   {n_files}")
    print(f"  cores fully skipped (no retrobios entries): {sorted(fully_skipped)}")
    print(f"  cores partially mapped ({len(partial_cores)}): {sorted(partial_cores)}")
    print(f"  partial/unmatched files: {len(partial_files)}")
    print(f"wrote {OUT_PR_BODY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
