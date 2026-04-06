# MiSTer FPGA BIOS Checker

Find out which BIOS files your MiSTer SD card is missing, with MD5 hashes you can Google to track them down.

| | Tool | When to use |
|---|---|---|
| Web | **[BIOS Checker](https://takiiiiiiii.github.io/MiSTer_FPGA_BIOS_Checker/)** | Open in a browser, pick your SD card's `games/` folder, and see what's present, missing, or wrong. Hashing is done locally, nothing gets uploaded. |
| Markdown | **[BIOS_LIST.md](./BIOS_LIST.md)** | Browse the full BIOS list with hashes right on GitHub. |
| Script | **[check_bios.sh](./scripts/check_bios.sh)** | Run directly on your MiSTer hardware. Writes a report to `/media/fat/bios_report.txt`. |

## Why?

MiSTer's BIOS database ([ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer)) is a zipped JSON meant for the Downloader tool. There's no way for a person to just look at it and see what they need. If you're missing a BIOS, the quickest way to find one is to Google its MD5 hash, but that hash is buried in the database.

This project puts all of that information in front of you. Every BIOS, every hash, with copy buttons and search links.

## Data sources

- **BiosDB** - [ajgowans/BiosDB_MiSTer](https://github.com/ajgowans/BiosDB_MiSTer), the community BIOS database used by MiSTer Downloader and Update All. Provides archive.org download links.
- **retrobios** - [Abdess/retrobios](https://github.com/Abdess/retrobios), a large multi-emulator BIOS collection. Cross-referenced by MD5 as a second download source in case archive.org is unavailable.

## Web checker

1. Go to **https://takiiiiiiii.github.io/MiSTer_FPGA_BIOS_Checker/**
2. Click **Scan my SD card** and pick your `games/` folder.
3. Each BIOS shows its status:
   - **Present** - file found, MD5 matches.
   - **Missing** - file not on your card.
   - **Wrong hash** - file exists but doesn't match the expected BIOS.
4. Click **Google hash** on any missing file to search for it.

All hashing happens in your browser. Nothing is uploaded anywhere.

## MiSTer script

```sh
wget -O /media/fat/Scripts/check_bios.sh \
  https://raw.githubusercontent.com/Takiiiiiiii/MiSTer_FPGA_BIOS_Checker/main/scripts/check_bios.sh
sh /media/fat/Scripts/check_bios.sh
cat /media/fat/bios_report.txt
```

Shows a checklist on screen and writes a detailed report with MD5 hashes for any missing files.

## Contributing

If you know a BIOS hash that should be included, PRs are welcome. Run `python3 build.py` to regenerate all outputs after making changes.

## License

Code is MIT-licensed. BIOS data is sourced from the community databases listed above at build time. No BIOS binaries are included in this repo.
