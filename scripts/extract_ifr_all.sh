#!/usr/bin/env bash
# Walk every PE32 body.bin in a UEFI extraction tree, run ifrextractor on each,
# copy any produced *.uefi.ifr.txt into ifr/<version>/_all/ with a stable name.
#
# Module-name resolution: use the parent directory name of the PE32 image
# section dir (which is the form "<index> <ModuleName>"). Strip leading
# "<index> " and use as canonical module name.
#
# Usage: extract_ifr_all.sh <version_tag> <dump_root>
# e.g.   extract_ifr_all.sh P3.80 extracted/all/P3.80/img.bin.dump

set -u

VERSION="${1:-}"
DUMP_ROOT="${2:-}"

if [[ -z "$VERSION" || -z "$DUMP_ROOT" ]]; then
    echo "usage: $0 <version_tag> <dump_root>" >&2
    exit 1
fi

OUT_DIR="$(realpath "$(dirname "$0")/..")/ifr/${VERSION}/_all"
mkdir -p "$OUT_DIR"

cd "$DUMP_ROOT" || exit 1

count=0
hit=0
# Find every PE32 image section's body.bin
while IFS= read -r -d '' pe32_body; do
    count=$((count + 1))
    # parent of "1 PE32 image section" is the module dir e.g. "72 Setup"
    pe32_dir="$(dirname "$pe32_body")"
    module_dir="$(dirname "$pe32_dir")"
    module_basename="$(basename "$module_dir")"

    # remove any pre-existing output to avoid stale matches
    rm -f "$pe32_dir"/body.bin.*.uefi.ifr.txt 2>/dev/null

    out=$(ifrextractor "$pe32_body" all 2>&1) || true

    # ifrextractor writes alongside body.bin
    shopt -s nullglob
    for ifr_out in "$pe32_dir"/body.bin.*.uefi.ifr.txt; do
        hit=$((hit + 1))
        # rename: <module_basename>.<idx>.uefi.ifr.txt -> sanitize spaces
        sanitized="$(echo "$module_basename" | tr ' /' '__')"
        # add suffix if multiple form/string packages
        suffix="$(basename "$ifr_out" | sed 's/^body\.bin//')"
        cp "$ifr_out" "$OUT_DIR/${sanitized}${suffix}"
    done
    shopt -u nullglob
done < <(find . -type f -name 'body.bin' -path '*/1 PE32 image section/body.bin' -print0)

echo "Scanned $count PE32 bodies, produced $hit IFR text files in $OUT_DIR"
ls "$OUT_DIR" | wc -l
