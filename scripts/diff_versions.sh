#!/usr/bin/env bash
# Cross-version diff of AGESA-relevant modules and APCB blobs.
# Output: docs/CROSS_VERSION_DIFF.md
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT="docs/CROSS_VERSION_DIFF.md"
VERS=(3.11 3.70 3.80 3.90 4.10)

# --- Locate body.bin for a named module in a given version ---
# Picks the largest match (the active-volume copy, not header/recovery shards).
mod_body() {
  local ver="$1" name="$2"
  find "extracted/all/P${ver}/img.bin.dump" \
    -path "*${name}/1 PE32 image section/body.bin" \
    -size +5k 2>/dev/null \
    | xargs -I{} ls -la "{}" 2>/dev/null \
    | sort -k5 -n | tail -1 | awk '{print $NF}'
}

# --- Hash a file (sha256, short) ---
sh() { sha256sum "$1" 2>/dev/null | cut -c1-12; }

# --- Module size + hash table ---
echo "Building module diff table..." >&2
{
  echo "# Cross-version diff: ROMED8-2T BIOS L3.11 / P3.70 / P3.80 / P3.90 / P4.10"
  echo
  echo "_Generated $(date -u +%Y-%m-%dT%H:%M:%SZ) by \`scripts/diff_versions.sh\`._"
  echo
  echo "## Image-level"
  echo
  echo "| Version | File | mtime | SHA256 (12) |"
  echo "|---|---|---|---|"
  for V in "${VERS[@]}"; do
    f="images/ROMD82T${V}"
    mt=$(stat -c%y "$f" | cut -d. -f1)
    h=$(sh "$f")
    echo "| L${V/3.11/3.11}P${V/3.11/} | \`ROMD82T${V}\` | $mt | \`$h\` |" 2>/dev/null || \
      echo "| ${V} | \`ROMD82T${V}\` | $mt | \`$h\` |"
  done
  # cleaner version line
  echo
  echo "## AGESA-relevant module SHA256 / size by version"
  echo
  echo "Modules of interest are those that contain AGESA logic relevant to PCIe link speed: NBIO PCIe, ALib, APCB, CPM PCIe init. \"=\" against the previous column means \"same hash as the previous version listed\"."
  echo
  modules=(
    "AmdNbioPcieDxe"
    "AmdNbioPciePei"
    "AmdNbioAlibDxe"
    "AmdNbioAlibZpDxe"
    "AmdNbioBaseSspDxe"
    "AmdNbioBaseGnDxe"
    "AmdCpmPcieInitDxe"
    "AmdCpmPcieInitPeim"
    "AmdApcbDxeV3"
    "AmdApcbSmmV3"
    "CbsSetupDxeSSP"
    "CbsSetupDxeZP"
    "CbsSetupDxeGN"
    "CbsBaseDxeSSP"
    "CbsBaseDxeZP"
    "CbsBasePeiSSP"
    "CbsBasePeiZP"
    "AmdNbioPciePei"
    "PcieInfoJudgeDxe"
    "Setup"
  )
  echo
  printf "| Module |"
  for V in "${VERS[@]}"; do printf " ${V/3.11/L3.11} |"; done
  echo
  printf "|---|"
  for V in "${VERS[@]}"; do printf "---|"; done
  echo
  for m in "${modules[@]}"; do
    printf "| \`%s\` |" "$m"
    prev=""
    for V in "${VERS[@]}"; do
      b=$(mod_body "$V" "$m")
      if [ -n "$b" ]; then
        s=$(stat -c%s "$b")
        h=$(sh "$b")
        if [ "$h" = "$prev" ]; then
          printf " = %s B |" "$s"
        else
          printf " %s · %s B |" "$h" "$s"
        fi
        prev="$h"
      else
        printf " — |"
        prev=""
      fi
    done
    echo
  done

  # --- APCB blobs (raw FFS files outside PE32 modules) ---
  echo
  echo "## APCB binary blobs"
  echo
  echo "AGESA's per-board PCIe (DXIO) descriptors live in the APCB binary, not in any PE32 module. APCB blobs are stored as raw FFS files identified by their AMD GUIDs. They are not user-visible or NVRAM-backed."
  echo

  # Common APCB GUIDs across AMD AGESA variants. Match by GUID-named directories under the dump tree.
  # (UEFIExtract names dirs by GUID when there's no UI section.)
  declare -A APCB_GUIDS=(
    ["APOB-Recovery"]            "F2C70C57-99A6-44A6-AC73-15F9C9DB9527"
    ["ApcbBackup"]               "0DCD9E04-5350-4A4A-8B61-B8B1FC83AB27"
    ["ApcbBackup-V3"]            "37B96AF6-A6E7-4D88-816B-3F3F5B66C492"
    ["ApcbBinary"]               "6C95E0A4-5BF7-4F14-9B98-DBEE6CFB6FC2"
    ["AmdApcbBinaryFile"]        "B68C6122-D75A-4D7C-A0CD-D8B4D38C6F40"
  )
  for label in "${!APCB_GUIDS[@]}"; do
    g="${APCB_GUIDS[$label]}"
    printf "### \`%s\` (GUID \`%s\`)\n\n" "$label" "$g"
    printf "| Version | size | sha256(12) |\n|---|---|---|\n"
    for V in "${VERS[@]}"; do
      b=$(find "extracted/all/P${V}/img.bin.dump" -type d -iname "*${g}*" 2>/dev/null \
          | head -1)
      if [ -n "$b" ]; then
        bin=$(find "$b" -name "body.bin" 2>/dev/null | head -1)
        if [ -n "$bin" ]; then
          printf "| %s | %s | %s |\n" "$V" "$(stat -c%s "$bin")" "$(sh "$bin")"
        else
          printf "| %s | (dir, no body) | |\n" "$V"
        fi
      else
        printf "| %s | (not found) | |\n" "$V"
      fi
    done
    echo
  done

  # --- Hunt for APCB header magic in raw image regions ---
  echo "## APCB magic byte scan in raw images"
  echo
  echo "APCB headers begin with the ASCII bytes \`APCB\` (0x41 0x50 0x43 0x42)."
  echo "Each row below is one offset where that magic appears in the raw image."
  echo
  for V in "${VERS[@]}"; do
    img="images/ROMD82T${V}"
    echo "### P${V/3.11/L3.11}"
    echo
    echo '```'
    grep -aob 'APCB' "$img" 2>/dev/null | head -20
    echo '```'
    echo
  done

  # --- Bytes 0x10 around each APCB occurrence in P3.70 vs P4.10 ---
  echo "## First APCB header bytes (16) — P3.70 vs P4.10"
  echo
  for V in 3.70 4.10; do
    echo "### P${V}"
    echo '```'
    img="images/ROMD82T${V}"
    grep -aob 'APCB' "$img" 2>/dev/null | head -5 | while IFS=: read off _; do
      hex=$(xxd -s "$off" -l 64 -g 1 "$img" | head -1)
      echo "@$off  $hex"
    done
    echo '```'
    echo
  done

  # --- DXIO descriptor markers ---
  echo "## DXIO descriptor signature scan"
  echo
  echo "The ASRock board's DXIO descriptors are typically embedded as a sub-blob inside an APCB-Group with a recognizable structural pattern. They start with byte sequences identifying \"DXIO Descriptor\" entries. Empirically, the 5-byte ASCII sequence \`PORT\` does not occur in AGESA descriptor binaries — but per-link Type/Subtype byte tuples do, and slot-naming strings sometimes appear."
  echo
  for V in "${VERS[@]}"; do
    img="images/ROMD82T${V}"
    n=$(grep -aoc 'PCIE\([1-9]\|10\|11\)' "$img" 2>/dev/null || true)
    echo "- P${V/3.11/L3.11}: 'PCIE[1..]' string occurrences in raw image: ${n:-0}"
  done
  echo

  echo "## Summary diff: which versions change which modules"
  echo
  echo "Run \`scripts/diff_versions.sh\` and inspect the table above. A module whose hash differs across versions is a candidate for behavior change between BIOS revisions. A module whose hash is identical across all versions had no source change in that span."
} > "$OUT"
echo "Wrote $OUT" >&2
