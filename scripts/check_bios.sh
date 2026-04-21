#!/bin/sh
# check_bios.sh - MiSTer BIOS scanner
# 60 BIOS entries, last updated 2026-04-20
#
# Checks your MiSTer SD card for missing or mismatched BIOS files
# and writes a report to /media/fat/bios_report.txt.
#
# Install:
#   wget -O /media/fat/Scripts/check_bios.sh \
#     https://raw.githubusercontent.com/Takiiiiiii/MiSTerFPGA-BIOS/main/scripts/check_bios.sh
#   sh /media/fat/Scripts/check_bios.sh

# 20260406: Add bootrom fallback with /games priority (Tonton)

MIST="/media/fat"
GAMES_DIR="${GAMES_DIR:-$MIST/games}"
REPORT="${REPORT:-$MIST/bios_report.txt}"

# Format: "<core>|<filename>|<target_path_relative_to_games>|<size>|<md5>"
ENTRIES="
3DO|boot.rom|3DO/boot.rom|1048576|f47264dd47fe30f73ab3c010015c155b
3DO|kanji.rom|3DO/kanji.rom|1048576|c23fb5d5e6bb1c240d02cf968972be37
Apple-IIgs|boot.rom|Apple-IIgs/boot.rom|262144|ba89edf2729a28a17cd9e0f7a0ac9a39
Apple-IIgs|boot1.rom|Apple-IIgs/boot1.rom|131072|20a0334c447cb069a040ae5be1d938df
Astrocade|boot.rom|Astrocade/boot.rom|8192|7d25a26e5c4841b364cfe6b1735eaf03
AtariLynx|boot.rom|AtariLynx/boot.rom|512|fcd403db69f54290b51035d82f835e7b
Casio_PV-2000|boot0.rom|Casio_PV-2000/boot0.rom|16384|558540c5c6f776d88a897f2f3b8fec8f
CD-i|boot0.rom|CD-i/boot0.rom|524288|2969341396aa61e0143dc2351aaa6ef6
CD-i|boot1.rom|CD-i/boot1.rom|8192|3d20cf7550f1b723158b42a1fd5bac62
CD-i|boot2.rom|CD-i/boot2.rom|131072|9694c466f9b65c1990a81b7a6280546b
COCO3|boot0.rom|COCO3/boot0.rom|32768|7233c6c429f3ce1c7392f28a933e0b6f
COCO3|boot1.rom|COCO3/boot1.rom|8192|8cab28f4b7311b8df63c07bb3b59bfd5
COCO3|boot2.rom|COCO3/boot2.rom|8192|171fb7a5d3b808565295b45c773abaaf
CreatiVision|boot.rom|CreatiVision/boot.rom|16384|4dfadfb1158f84e2df2b85b13f303986
Gamate|boot.rom|Gamate/boot.rom|4096|ef67993a94503c4b7798b5901c7dda52
GAMEBOY|boot1.rom|GAMEBOY/boot1.rom|2304|dbfce9db9deaa2567f6a84fde55f9680
GBA|boot.rom|GBA/boot.rom|16384|a860e8c0b6d573d191e4ec7db1b1e4f6
Intellivision|boot0.rom|Intellivision/boot0.rom|8192|62e761035cb657903761800f4437b8af
Intellivision|boot1.rom|Intellivision/boot1.rom|2048|0cd5946c6473e42e8e4c2137785e427f
Intellivision|boot2.rom|Intellivision/boot2.rom|2048|d5530f74681ec6e0f282dab42e6b1c5f
Intellivision|boot3.rom|Intellivision/boot3.rom|24576|2e72a9a2b897d330a35c8b07a6146c52
Interact|boot.rom|Interact/boot.rom|2048|aa9fb0e9697a009dfb9d876351dd8f48
Jaguar|boot.rom|Jaguar/boot.rom|131072|6e844759720226e58d55ecaf33608a13
Jaguar|boot1.rom|Jaguar/boot1.rom|262144|18f0741bdb8bb9b6bb99393cb90426a2
Jaguar|boot2.rom|Jaguar/boot2.rom|131072|4af00f1c26898cf04585e1693d25faba
MegaCD|boot.rom|MegaCD/boot.rom|131072|14db9657bbaa6fbb9249752424dc0ce4
MegaCD|cd_bios.rom|MegaCD/Europe/cd_bios.rom|131072|9b562ebf2d095bf1dabadbc1881f519a
MegaCD|cd_bios.rom|MegaCD/Japan/cd_bios.rom|131072|683a8a9e273662561172468dfa2858eb
MegaCD|cd_bios.rom|MegaCD/USA/cd_bios.rom|131072|310a9081d2edf2d316ab38813136725e
MSX1|boot.rom|MSX1/boot.rom|32768|a0452dbf5ace7d2e49d0a8029efed09a
N64|boot.rom|N64/boot.rom|1984|5c124e7948ada85da603a522782940d0
N64|boot1.rom|N64/boot1.rom|1984|d4232dc935cad0650ac2664d52281f3a
NEOGEO|000-lo.lo|NEOGEO/000-lo.lo|131072|fc7599f3f871578fe9a0453662d1c966
NEOGEO|neo-epo.sp1|NEOGEO/neo-epo.sp1|131072|b11751ad42879c461d64ad2b7b2b0129
NEOGEO|sfix.sfix|NEOGEO/sfix.sfix|131072|aa2b5d0eae4158ffc0d7d63481c7830b
NEOGEO|sp-s2.sp1|NEOGEO/sp-s2.sp1|131072|2968f59f44bf328639aa79391aeeeab4
NEOGEO|uni-bios.rom|NEOGEO/uni-bios.rom|131072|4f0aeda8d2d145f596826b62d563c4ef
NeoGeo-CD|neocd.bin|NeoGeo-CD/neocd.bin|524288|f39572af7584cb5b3f70ae8cc848aba2
NeoGeo-CD|top-sp1.bin|NeoGeo-CD/top-sp1.bin|524288|122aee210324c72e8a11116e6ef9c0d0
NeoGeo-CD|uni-bioscd.rom|NeoGeo-CD/uni-bioscd.rom|524288|08ca8b2dba6662e8024f9e789711c6fc
NES|boot0.rom|NES/boot0.rom|8192|ca30b50f880eb660a320674ed365ef7a
PC8801|boot.rom|PC8801/boot.rom|393216|f1ce4d5f83717093982e5f75516b8f3c
PocketChallengeV2|boot.rom|PocketChallengeV2/boot.rom|4096|54b915694731cc22e07d3fb8a00ee2db
PocketChallengeV2|boot1.rom|PocketChallengeV2/boot1.rom|8192|880893bd5a7d53fff826bd76a83d566e
PokemonMini|boot.rom|PokemonMini/boot.rom|4096|1e4fb124a3a886865acb574f388c803d
PSX|boot.rom|PSX/boot.rom|524288|1e68c231d0896b7eadcad1d7d8e76129
PSX|boot1.rom|PSX/boot1.rom|524288|8e4c14f567745eff2f0408c8129f72a6
PSX|boot2.rom|PSX/boot2.rom|524288|b9d9a0286c33dc6b7237bb13cd46fdee
PSX|sbi.zip|PSX/sbi.zip|218953|706d60ab2dfdbfdd53be2069cb85a1fe
Saturn|boot.rom|Saturn/boot.rom|524288|0306c0e408d6682dd2d86324bd4ac661
SCV|boot.rom|SCV/boot.rom|6144|b596975be2e0360232bbeb1e492ab873
SGB|Super Game Boy 2.sfc|SGB/Super Game Boy 2.sfc|524288|8ecd73eb4edf7ed7e81aef1be80031d5
SGB|Super Game Boy.sfc|SGB/Super Game Boy.sfc|262144|b15ddb15721c657d82c5bab6db982ee9
SNES|bsx_bios.rom|SNES/bsx_bios.rom|1048576|96cf17bf589fcbfa6f8de2dc84f19fa2
TGFX16-CD|cd_bios.rom|TGFX16-CD/cd_bios.rom|262144|98d43a097a165b03df170fd5c2ad2c2f
TI-99_4A|boot0.rom|TI-99_4A/boot0.rom|196608|a75bb208176c0aed1b6a04b2dcf4770c
WonderSwan|boot.rom|WonderSwan/boot.rom|4096|54b915694731cc22e07d3fb8a00ee2db
WonderSwan|boot1.rom|WonderSwan/boot1.rom|8192|880893bd5a7d53fff826bd76a83d566e
WonderSwanColor|boot.rom|WonderSwanColor/boot.rom|4096|54b915694731cc22e07d3fb8a00ee2db
WonderSwanColor|boot1.rom|WonderSwanColor/boot1.rom|8192|880893bd5a7d53fff826bd76a83d566e
"


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
    alt="${core}.rom"
    alt_path="$MIST/bootrom/$alt"
    check_path="$full_path"

    if [ ! -f "$full_path" ]; then
        check_path="$alt_path"
        if [ ! -f "$alt_path" ]; then
            missing_list="$missing_list$core|$filename|$rel|$expected_size|$expected_md5
            "
            continue
        fi
    fi

    actual_md5=$(md5sum "$check_path" 2>/dev/null | cut -d' ' -f1)
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
