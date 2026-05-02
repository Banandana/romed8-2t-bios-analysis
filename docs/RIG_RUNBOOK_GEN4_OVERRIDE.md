# Rig Runbook — `LC_TARGET_LINK_SPEED_OVERRIDE` Gen4 retrain experiment

> # DO NOT RUN THIS WITHOUT EXPLICIT USER AUTHORIZATION
>
> The rig is an 8x RTX 3090 vLLM production node. This runbook
> performs SMN writes to NBIO PCIe link-speed registers and triggers a PCIe
> retrain on **one** GPU root port. Worst-case outcomes include: GPU dropping
> off the bus, kernel MCE, vLLM workers crashing across all 8 GPUs (TP=8 means
> one missing rank kills the engine), `nvidia-smi` hang, and in rare cases a
> reboot to recover. Do not begin without:
>
> 1. Explicit user (banandana) authorization for this specific runbook.
> 2. vLLM stopped or in a maintenance window. `systemctl stop` whatever serves
>    the model. Do not run while requests are in-flight.
> 3. A second SSH session held open (the primary may hang if an MCE storms).
> 4. BMC/IPMI reachable for out-of-band reboot.
> 5. The user agreeing in advance that "test outcome is Gen3" is the expected
>    answer and that "Gen4 succeeded" is the surprise. If the strong prior holds
>    we learn nothing and the rig is unchanged; the cost is the maintenance
>    window itself.
>
> Read the entire runbook before starting. Do not skip the rollback section.
>
> Test target: **one** GPU root port only. Initially ruled-in target is the
> port hosting the GPU with the most-marginal PCIe state (highest LnkSta2 EQ
> phase, or the GPU that already shows Xid issues — i.e. **GPU 7**). Confirm
> BDF in step 1 before writing.

---

## Background (why this experiment, what is hypothesised)

The PCIe Gen3 cap on the 8 GPU root ports is enforced by
`PCIE_LC_SPEED_CNTL.LC_GEN4_EN_STRAP=0` (bit 2, SMN `0x111402A4` per IOHC
stride), which is `HwInit`-typed and locked at PSP cold boot from APCB DXIO
descriptors. See `docs/PPR_REGISTER_NOTES.md` for the full register reference.

`LC_TARGET_LINK_SPEED_OVERRIDE_EN` (bit 11) and `LC_TARGET_LINK_SPEED_OVERRIDE`
(bits 12-14) of the same register are documented as RW. AMD's amdgpu driver
writes them at runtime. **The strong prior is that the override is honored
only within the rate set enabled by the `GEN_EN` straps** — i.e. with
`GEN4_EN_STRAP=0`, override=4 (Gen4) silently negotiates Gen3 because
TS1/TS2 ordered sets advertise only Gen3.

**The PPR text on whether the strap masks the override directly was not
retrievable** during Phase 1 (AMD CDN no longer serves the PDF). This
experiment is the empirical resolution. Cheap, definitive in the negative
(expected), spectacular in the positive (unlikely).

---

## Step 1 — Prerequisites check

Run all of these and capture the output to a baseline file. **Do not proceed
if any check fails.**

```bash
# Working directory + log file
mkdir -p /root/gen4_experiment
cd /root/gen4_experiment
LOG=/root/gen4_experiment/baseline_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

echo "=== identity & kernel ==="
id
uname -a
cat /proc/cmdline
cat /sys/devices/system/cpu/online

echo "=== kernel lockdown ==="
cat /sys/kernel/security/lockdown 2>/dev/null || echo "no lockdown LSM"
# Expected: "[none] integrity confidentiality" (none active).
# If active: this experiment requires lockdown=none; reboot with
# 'lockdown=none' on cmdline, OR use a kernel module (out of scope here).

echo "=== /dev/mem accessibility ==="
ls -l /dev/mem
# CONFIG_STRICT_DEVMEM may restrict /dev/mem even as root. Check:
zcat /proc/config.gz 2>/dev/null | grep -E 'STRICT_DEVMEM|IO_STRICT|LOCKDOWN' \
   || cat /boot/config-$(uname -r) | grep -E 'STRICT_DEVMEM|IO_STRICT|LOCKDOWN'
# CONFIG_STRICT_DEVMEM=y is the typical case. If so, this runbook's setpci-only
# path still works (config space is reachable via setpci regardless). Direct
# /dev/mem MMIO is NOT used here — all SMN writes go through PCI cfg 0x60/0x64
# on the root bridge, which setpci can do.

echo "=== required tools ==="
which setpci lspci dmesg awk tee
setpci --version
lspci --version

echo "=== AMD root bridge (SMN access path) ==="
# DID 0x1450 = AMD Family 17h NB (data fabric / root bridge), one per node.
# This is the device that has SMN index/data at config 0x60/0x64.
lspci -d 1022:1450 -nn
# Expected on EPYC 7532 (single socket Rome): four functions at 00:00.x or similar.
# The exact bridge BDF for SMN access is the F0 of the IOMS — confirm via:
lspci -d 1022:1450 -vv | grep -E 'Device|Subsystem'

echo "=== current GPU root ports (LnkCap2/LnkCtl2/LnkSta) ==="
# Identify all 8 GPU root ports + the Gen4-capable 40:01.3 reference port.
for bdf in $(lspci -nn | grep -E 'Bridge.*1022:14[a-f]b' | awk '{print $1}'); do
  echo "--- $bdf ---"
  lspci -vv -s "$bdf" 2>/dev/null | grep -E 'LnkCap|LnkCtl2|LnkSta' | head -10
done

echo "=== smm/MCE baseline ==="
dmesg | grep -iE 'smm|mce|hardware error' | tail -20

echo "=== currently loaded GPU driver ==="
lsmod | grep -E '^nvidia'
nvidia-smi -L 2>/dev/null || echo "nvidia-smi not loaded or no GPUs visible"
```

**Pass criteria:**
- `id` reports `uid=0`.
- Kernel lockdown is `none`.
- `setpci` and `lspci` are present and recent (util-linux setpci is fine).
- `lspci -d 1022:1450` returns at least one device.
- All 8 GPU root ports report `LnkCap2: 2.5-8GT/s` (current Gen3 cap, sanity).
- `dmesg` baseline has no recent MCE.

**Fail any of these → stop. Do not continue. Report which check failed.**

---

## Step 2 — Capture full baseline state

```bash
BASELINE=/root/gen4_experiment/preexp_$(date +%Y%m%d_%H%M%S).snapshot
exec > "$BASELINE" 2>&1

echo "=== timestamp ==="
date -Iseconds

echo "=== full lspci tree ==="
lspci -tvv

echo "=== per-GPU-root-port config snapshot ==="
# All 8 GPU root ports + the Gen4 reference port 40:01.3 + the chosen test target.
# Update GPU_PORTS list once Step 1 has confirmed actual BDFs.
GPU_PORTS=(
  # Fill these from `lspci -nn | grep '1022:14[a-f]b'` output in step 1.
  # Replace placeholders with actual bus:dev.fn strings.
  # Example for ROMED8-2T (typical layout):
  # 0000:20:01.1   # PCIE1
  # 0000:20:03.1   # PCIE2 / OCU lanes
  # 0000:40:01.1   # PCIE3 / PCIE4
  # 0000:40:03.1   # PCIE5
  # 0000:60:01.1   # PCIE6
  # 0000:60:03.1   # PCIE7
  # 0000:80:01.1   # M2_1
  # 0000:80:03.1   # M2_2
)
REF_PORT=0000:40:01.3   # the one Gen4-capable non-slot port (reference)

for bdf in "${GPU_PORTS[@]}" "$REF_PORT"; do
  echo "=== $bdf ==="
  lspci -vv -s "$bdf"
  echo "--- raw cfg bytes 0x00..0xFF ---"
  setpci -s "$bdf" 00.l 04.l 08.l 0c.l 10.l 14.l 18.l 1c.l 20.l 24.l \
                    28.l 2c.l 30.l 34.l 38.l 3c.l 40.l 44.l 48.l 4c.l \
                    50.l 54.l 58.l 5c.l 60.l 64.l 68.l 6c.l 70.l 74.l \
                    78.l 7c.l 80.l 84.l 88.l 8c.l 90.l 94.l 98.l 9c.l \
                    a0.l a4.l a8.l ac.l b0.l b4.l b8.l bc.l c0.l c4.l \
                    c8.l cc.l d0.l d4.l d8.l dc.l e0.l e4.l e8.l ec.l \
                    f0.l f4.l f8.l fc.l
  echo "--- key PCIe-cap fields (cap base resolved by setpci CAP_EXP) ---"
  echo -n "LnkCap (CAP_EXP+0c): " ; setpci -s "$bdf" CAP_EXP+0c.l
  echo -n "LnkCtl (CAP_EXP+10): " ; setpci -s "$bdf" CAP_EXP+10.w
  echo -n "LnkSta (CAP_EXP+12): " ; setpci -s "$bdf" CAP_EXP+12.w
  echo -n "LnkCap2(CAP_EXP+2c): " ; setpci -s "$bdf" CAP_EXP+2c.l
  echo -n "LnkCtl2(CAP_EXP+30): " ; setpci -s "$bdf" CAP_EXP+30.w
  echo -n "LnkSta2(CAP_EXP+32): " ; setpci -s "$bdf" CAP_EXP+32.w
done

echo "=== root bridge (SMN access) ==="
# Confirm the AMD root bridge (DID 0x1450) BDF used for SMN index/data.
# On Rome single-socket there is typically one per IOMS — pick the one whose
# bus number matches the test target's bus.
lspci -d 1022:1450 -nn

echo "=== nvidia state ==="
nvidia-smi --query-gpu=index,name,bus_id,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv
```

**Save the entire snapshot file off-host before continuing** (e.g.
`scp $BASELINE other-machine:`). If recovery requires a clean reference, this
file is it.

---

## Step 3 — Choose the single test target

**Constraints:**
- Must be a GPU root port. Do not target the BMC bridge or X550 NIC.
- Prefer the GPU that is least production-critical or already exhibiting
  issues. Per `BIOS_LATEST.md`, **GPU 7 has recurring Xid 79** at Gen3 — its
  link is already marginal, so a failed retrain is the lowest-cost outcome
  there.
- Identify the root port hosting GPU 7 by walking `lspci -tvv` from the GPU
  endpoint up to its parent bridge.

```bash
# Find GPU 7 endpoint BDF
nvidia-smi --query-gpu=index,bus_id --format=csv,noheader | grep '^7,'
# Output example: 7, 00000000:81:00.0
# So GPU 7 endpoint is 0000:81:00.0. Its parent root port is found via:
GPU7_EP=0000:81:00.0
PARENT=$(basename $(dirname $(readlink -f /sys/bus/pci/devices/$GPU7_EP)))
echo "Test target root port: $PARENT"

# Sanity: verify it is a 1022:14[a-f]b NBIO root port
lspci -nn -s "$PARENT"
```

**Set this as the test target:**

```bash
TEST_BDF="$PARENT"   # e.g. 0000:80:01.1
echo "TEST_BDF=$TEST_BDF" | tee /root/gen4_experiment/target.env
```

If GPU 7 turns out to be on a port that shares an IOMS with other GPUs whose
descriptors might be co-affected by the SMN write, **stop and reconsider**. On
Rome each NBIO root port has its own `PCIE_LC_SPEED_CNTL` instance at its own
SMN address, so co-effect is unlikely — but verify by reading bus topology
before writing.

---

## Step 4 — The override write sequence

### 4a. Compute SMN addresses for the test target

Per `docs/PPR_REGISTER_NOTES.md`:

- **`PCIE_LC_SPEED_CNTL`** = SMN base + DWORD `0x100A4`
  - Base for PCIe core block on F17h M31h: `0x11100000` per controller.
  - Per-IOHC stride: each IOHC's PCIe core is at a distinct SMN base.
  - Resolved address for IOHC0 PCIE0: `0x111402A4`.
  - **Per-port stride** within a controller: `+0x1000` per port index.

- **`PCIE_LC_SPEED_CNTL2`** = SMN base + DWORD `0x10105`
  - Byte offset from same base: `0x10105 * 4 - 0x40000` = `0x414` (relative
    to controller register window). For IOHC0 PCIE0: `0x11100000 + 0x10414` =
    **`0x11110414`** *(verify by reading first; this offset arithmetic was
    not double-checked against silicon)*.

**The exact SMN base for the IOMS hosting `TEST_BDF` must be derived from
the bus number.** Rome's IOMS layout maps bus number ranges to IOHC
instances. Approximate mapping for ROMED8-2T (single socket, NPS=1):

| Bus range  | IOHC | PCIe controller SMN base |
|------------|------|--------------------------|
| 00:        | IOHC0 | `0x11100000` |
| 20:        | IOHC1 | `0x11300000` |
| 40:        | IOHC2 | `0x11500000` |
| 60:        | IOHC3 | `0x11700000` |
| 80:        | IOHC4 | `0x11900000` (or wraps — verify) |

> **Caveat:** the IOHC<->bus-base mapping above is the published Rome convention
> but **has not been verified on this specific board**. The runbook operator
> MUST verify by:
>  1. Reading `PCIE_LC_SPEED_CNTL` first (Step 4b) and confirming the read
>     value is plausible (LC_GEN3_EN_STRAP=1 bit 1, LC_GEN4_EN_STRAP=0 bit 2).
>  2. Cross-checking with `lspci -t` topology.
> If the read returns `0xFFFFFFFF` or `0x00000000`, the SMN address is wrong;
> stop and recompute.

For the rest of this runbook, define:

```bash
# Replace with the verified SMN base for TEST_BDF's IOHC.
SMN_LC_SPEED_CNTL=0x11700a4    # placeholder example for IOHC3 PCIE0
# Or build from base + 0x402A4:
# SMN_BASE_IOHC3=0x11700000
# SMN_LC_SPEED_CNTL=$((SMN_BASE_IOHC3 + 0x402A4))   # 0x117402A4
SMN_LC_SPEED_CNTL2=$((SMN_LC_SPEED_CNTL - 0x402A4 + 0x10414))
# Add per-port stride if test target is not port 0 of the controller:
PORT_STRIDE=0x1000
PORT_INDEX=1   # determine from TEST_BDF dev.fn — typically dev.fn 01.1 is port 1
SMN_LC_SPEED_CNTL=$(( SMN_LC_SPEED_CNTL + PORT_INDEX * PORT_STRIDE ))
SMN_LC_SPEED_CNTL2=$(( SMN_LC_SPEED_CNTL2 + PORT_INDEX * PORT_STRIDE ))

printf "SMN_LC_SPEED_CNTL  = 0x%08x\n" "$SMN_LC_SPEED_CNTL"
printf "SMN_LC_SPEED_CNTL2 = 0x%08x\n" "$SMN_LC_SPEED_CNTL2"
```

### 4b. Define SMN read/write helpers (via root bridge cfg 0x60/0x64)

The root bridge at DID `1022:1450` carries SMN index/data at config offsets
`0x60` (write the SMN address), `0x64` (read/write the data). **Pick the F0
function whose bus matches `TEST_BDF`'s IOMS** — usually the same `IOMS_BUS:00.0`
device.

```bash
# Find the matching root bridge for TEST_BDF.
# Strategy: pick the 1022:1450 device on the same root complex as TEST_BDF.
# On Rome there is one per IOMS at <bus>:00.0 typically.
ROOT_BDF=0000:00:00.2        # placeholder — replace with the verified F0
# Verify:
lspci -nn -s "$ROOT_BDF"
# Should show 1022:1450 (Family 17h Data Fabric Function 0 / SMN host).

smn_read () {
  local addr=$1
  printf -v hex '%08x' "$addr"
  setpci -s "$ROOT_BDF" 60.l="$hex" >/dev/null
  setpci -s "$ROOT_BDF" 64.l
}

smn_write () {
  local addr=$1 val=$2
  printf -v ahex '%08x' "$addr"
  printf -v vhex '%08x' "$val"
  setpci -s "$ROOT_BDF" 60.l="$ahex" >/dev/null
  setpci -s "$ROOT_BDF" 64.l="$vhex" >/dev/null
}
```

> **CRITICAL serialization warning:** SMN access via PCI cfg 0x60/0x64 is
> NOT atomic from userspace — another process touching the same root bridge
> between the index write and the data access will corrupt the access. This
> is why kernel `amd_smn_read()` takes a per-node mutex. For this runbook,
> the operator MUST ensure no concurrent SMN-using tools are running:
> stop AMD-IOPM-UTIL, k10temp polling at high frequency, anything that
> touches the AMD root bridge. `lsof /proc/bus/pci` + `fuser` for sanity.

### 4c. Read current `PCIE_LC_SPEED_CNTL` (sanity)

```bash
ORIG_LCSC=$(smn_read $SMN_LC_SPEED_CNTL)
echo "Original LC_SPEED_CNTL = $ORIG_LCSC"
# Expected: bit 1 (GEN3_EN) = 1, bit 2 (GEN4_EN) = 0 for the GPU root ports.
# Decode:
ORIG=$((16#${ORIG_LCSC#0x}))
printf "  GEN2_EN_STRAP (bit 0): %d\n" $(( (ORIG >> 0) & 1 ))
printf "  GEN3_EN_STRAP (bit 1): %d\n" $(( (ORIG >> 1) & 1 ))
printf "  GEN4_EN_STRAP (bit 2): %d\n" $(( (ORIG >> 2) & 1 ))
printf "  GEN5_EN_STRAP (bit 3): %d\n" $(( (ORIG >> 3) & 1 ))
printf "  CURRENT_DATA_RATE (5-7): %d\n" $(( (ORIG >> 5) & 7 ))
printf "  TARGET_LINK_SPEED_OVERRIDE_EN (bit 11): %d\n" $(( (ORIG >> 11) & 1 ))
printf "  TARGET_LINK_SPEED_OVERRIDE   (bits 12-14): %d\n" $(( (ORIG >> 12) & 7 ))

ORIG_LCSC2=$(smn_read $SMN_LC_SPEED_CNTL2)
echo "Original LC_SPEED_CNTL2 = $ORIG_LCSC2"
ORIG2=$((16#${ORIG_LCSC2#0x}))
printf "  FORCE_EN_SW_SPEED_CHANGE  (bit 0): %d\n" $(( (ORIG2 >> 0) & 1 ))
printf "  FORCE_DIS_SW_SPEED_CHANGE (bit 1): %d\n" $(( (ORIG2 >> 1) & 1 ))
printf "  FORCE_EN_HW_SPEED_CHANGE  (bit 2): %d\n" $(( (ORIG2 >> 2) & 1 ))
printf "  FORCE_DIS_HW_SPEED_CHANGE (bit 3): %d\n" $(( (ORIG2 >> 3) & 1 ))
printf "  INITIATE_LINK_SPEED_CHANGE (bit 6): %d\n" $(( (ORIG2 >> 6) & 1 ))
printf "  SPEED_CHANGE_STATUS (bit 7): %d\n" $(( (ORIG2 >> 7) & 1 ))

# Save originals for rollback
echo "ORIG_LCSC=$ORIG_LCSC"  >  /root/gen4_experiment/orig.env
echo "ORIG_LCSC2=$ORIG_LCSC2" >> /root/gen4_experiment/orig.env
echo "SMN_LC_SPEED_CNTL=$(printf 0x%08x $SMN_LC_SPEED_CNTL)"   >> /root/gen4_experiment/orig.env
echo "SMN_LC_SPEED_CNTL2=$(printf 0x%08x $SMN_LC_SPEED_CNTL2)" >> /root/gen4_experiment/orig.env
echo "ROOT_BDF=$ROOT_BDF"      >> /root/gen4_experiment/orig.env
echo "TEST_BDF=$TEST_BDF"      >> /root/gen4_experiment/orig.env
```

**Sanity gates before continuing:**
- `GEN3_EN_STRAP == 1` (Gen3 enabled).
- `GEN4_EN_STRAP == 0` (the cap we're trying to circumvent).
- `TARGET_LINK_SPEED_OVERRIDE_EN == 0` (no existing override).
- `CURRENT_DATA_RATE` ∈ {1, 3} (Gen1 idle or Gen3 active).
- `LC_SPEED_CNTL2.FORCE_DIS_*` bits all zero (nothing already forcing).

If any of these are unexpected: stop, re-derive SMN addresses, do not write.

### 4d. Write the override sequence

Compute new register values:

```bash
NEW_LCSC=$(( ORIG | (1 << 11) | (4 << 12) ))    # set OVERRIDE_EN, OVERRIDE=4 (Gen4)
NEW_LCSC=$(( NEW_LCSC & ~(7 << 12) ))           # clear bits 12-14 first...
NEW_LCSC=$(( NEW_LCSC | (4 << 12) | (1 << 11) )) # ...then set OVERRIDE=4 + OVERRIDE_EN=1

NEW_LCSC2=$(( ORIG2 | (1 << 2) ))               # FORCE_EN_HW_SPEED_CHANGE = 1

printf "Will write LC_SPEED_CNTL  = 0x%08x  (was $ORIG_LCSC)\n" "$NEW_LCSC"
printf "Will write LC_SPEED_CNTL2 = 0x%08x  (was $ORIG_LCSC2)\n" "$NEW_LCSC2"
echo
echo "Press ENTER to proceed, Ctrl-C to abort."
read
```

Write:

```bash
echo "[$(date -Iseconds)] writing LC_SPEED_CNTL"
smn_write $SMN_LC_SPEED_CNTL $NEW_LCSC

echo "[$(date -Iseconds)] writing LC_SPEED_CNTL2"
smn_write $SMN_LC_SPEED_CNTL2 $NEW_LCSC2

# Read back and confirm the writes landed.
RB1=$(smn_read $SMN_LC_SPEED_CNTL)
RB2=$(smn_read $SMN_LC_SPEED_CNTL2)
echo "Readback LC_SPEED_CNTL  = $RB1"
echo "Readback LC_SPEED_CNTL2 = $RB2"
# If RB1 still shows OVERRIDE_EN=0 / OVERRIDE!=4, the SMN write was filtered
# (HwInit guard or SMN firewall). This is itself the experimental answer:
# the override bits are not actually RW on this silicon. Skip Step 4e and
# go to rollback.
```

### 4e. Trigger PCIe retrain on the test port

```bash
# PCIe LCTL: set "Retrain Link" bit (cap-relative offset 0x10, bit 5).
echo "[$(date -Iseconds)] triggering retrain on $TEST_BDF"
LCTL_BEFORE=$(setpci -s "$TEST_BDF" CAP_EXP+10.w)
echo "  LCTL before: $LCTL_BEFORE"
# Set bit 5 (retrain). Use OR semantics: write old | 0x20.
NEW_LCTL=$(printf '%04x' $(( 16#$LCTL_BEFORE | 0x20 )))
setpci -s "$TEST_BDF" CAP_EXP+10.w="$NEW_LCTL"

# Also set LCTL2 Target Link Speed = 4 (Gen4) for completeness.
LCTL2_BEFORE=$(setpci -s "$TEST_BDF" CAP_EXP+30.w)
echo "  LCTL2 before: $LCTL2_BEFORE"
NEW_LCTL2=$(printf '%04x' $(( (16#$LCTL2_BEFORE & ~0xF) | 0x4 )))
setpci -s "$TEST_BDF" CAP_EXP+30.w="$NEW_LCTL2"

# Wait for retrain.
sleep 0.2
```

---

## Step 5 — Post-write verification

```bash
echo "=== post-retrain state on $TEST_BDF ==="
lspci -vv -s "$TEST_BDF" | grep -E 'LnkCap|LnkCtl2|LnkSta'

echo "=== LC_SPEED_CNTL after retrain ==="
POST_LCSC=$(smn_read $SMN_LC_SPEED_CNTL)
POST=$((16#${POST_LCSC#0x}))
printf "  CURRENT_DATA_RATE: %d  (1=Gen1 2=Gen2 3=Gen3 4=Gen4)\n" \
       $(( (POST >> 5) & 7 ))
printf "  DATA_RATE_ADVERTISED (8-10): %d\n" $(( (POST >> 8) & 7 ))

echo "=== LC_SPEED_CNTL2 after retrain ==="
POST_LCSC2=$(smn_read $SMN_LC_SPEED_CNTL2)
POST2=$((16#${POST_LCSC2#0x}))
printf "  SPEED_CHANGE_STATUS (bit 7): %d\n" $(( (POST2 >> 7) & 1 ))
printf "  ATTEMPT_FAILED      (bit 10): %d\n" $(( (POST2 >> 10) & 1 ))

echo "=== kernel log since experiment start ==="
dmesg --since='2 minutes ago' | tail -50
# Look for: AER errors, MCE, "pcieport ... link down", "nvidia: Xid", "GPU has fallen off the bus".

echo "=== nvidia state ==="
nvidia-smi -L
nvidia-smi --query-gpu=index,bus_id,pcie.link.gen.current,pcie.link.width.current --format=csv
```

**Outcome interpretation:**

| Result | Meaning |
|---|---|
| `LnkSta: Speed 8GT/s` (Gen3, current behavior) | Strap mask is hard. Override silently negotiated within strap-enabled rate set. **Expected outcome.** Experiment confirms the wall. |
| `LnkSta: Speed 16GT/s` (Gen4) | Strap is advertisement-mask only, not a hard rate clamp. **Surprise.** The runtime override bypasses the cap. Document immediately, do NOT assume stable until soak-tested. Re-run for all 8 ports only after a full vLLM workload soak on this single port. |
| `LnkSta: Speed <Gen3` / link down / GPU vanished | Retrain failed catastrophically. **Go to rollback immediately.** |
| `dmesg` shows MCE / AER fatal | Hardware-error storm; rollback then reboot. The cap returns at boot regardless. |
| SMN readback shows the override bits stuck at 0 | SMN write was filtered (HwInit attribute is enforced more broadly than expected, or SMN firewall blocked it). The experimental answer is "SMN-write rejected." Rollback (no-op since write didn't take) and document. |

---

## Step 6 — Rollback (always run, even on success)

The override bits do NOT auto-revert on link-down. Explicit clear is required.

```bash
source /root/gen4_experiment/orig.env

echo "[$(date -Iseconds)] restoring LC_SPEED_CNTL2 to $ORIG_LCSC2"
smn_write $SMN_LC_SPEED_CNTL2 $((16#${ORIG_LCSC2#0x}))

echo "[$(date -Iseconds)] restoring LC_SPEED_CNTL to $ORIG_LCSC"
smn_write $SMN_LC_SPEED_CNTL $((16#${ORIG_LCSC#0x}))

# Re-read to confirm.
echo "Readback LC_SPEED_CNTL  = $(smn_read $SMN_LC_SPEED_CNTL)   (expect $ORIG_LCSC)"
echo "Readback LC_SPEED_CNTL2 = $(smn_read $SMN_LC_SPEED_CNTL2)  (expect $ORIG_LCSC2)"

# Trigger one more retrain to settle into Gen3.
LCTL_NOW=$(setpci -s "$TEST_BDF" CAP_EXP+10.w)
NEW=$(printf '%04x' $(( 16#$LCTL_NOW | 0x20 )))
setpci -s "$TEST_BDF" CAP_EXP+10.w="$NEW"
sleep 0.2

# Restore LCTL2 Target Link Speed to its original value.
setpci -s "$TEST_BDF" CAP_EXP+30.w="$LCTL2_BEFORE"

# Final state check.
lspci -vv -s "$TEST_BDF" | grep -E 'LnkCap|LnkCtl2|LnkSta'
nvidia-smi -L
```

If `nvidia-smi` does not list the GPU on the test port after rollback:

```bash
# Try secondary bus reset on the parent bridge.
echo "[$(date -Iseconds)] secondary bus reset"
setpci -s "$TEST_BDF" BRIDGE_CONTROL.w=$(printf '%04x' \
    $(( $(setpci -s "$TEST_BDF" BRIDGE_CONTROL.w | tr -d ':') | 0x40 )))
sleep 0.1
setpci -s "$TEST_BDF" BRIDGE_CONTROL.w=$(printf '%04x' \
    $(( $(setpci -s "$TEST_BDF" BRIDGE_CONTROL.w | tr -d ':') & ~0x40 )))
sleep 1
echo 1 > /sys/bus/pci/rescan

# Then unbind/rebind nvidia.
GPU7_EP=0000:81:00.0   # adjust to actual endpoint
echo "$GPU7_EP" > /sys/bus/pci/drivers/nvidia/unbind 2>/dev/null
echo "$GPU7_EP" > /sys/bus/pci/drivers/nvidia/bind   2>/dev/null

nvidia-smi -L
```

If GPU is still missing after rescan + driver rebind: **reboot via BMC IPMI.**
The strap-locked Gen3 cap returns at cold boot; system will come back identical
to baseline.

---

## Step 7 — Failure modes & mitigations (reference)

| Failure | Symptom | Mitigation |
|---|---|---|
| GPU vanishes from `lspci` | `nvidia-smi -L` shows N-1 GPUs | secondary bus reset (Step 6) → PCI rescan → driver rebind. If still missing: BMC reboot. |
| Kernel MCE storm | `dmesg` flooded with `mce: ... Hardware error`; system may freeze | Hold second SSH session — issue `sync; sync; reboot` if responsive; otherwise BMC `power cycle`. The cap returns at boot. |
| `nvidia-smi` hangs | Other GPUs still visible, but `nvidia-smi` blocks indefinitely | nvidia driver waiting on the dropped port. Run rollback in second session, then `rmmod nvidia_uvm nvidia_drm nvidia_modeset nvidia` and `modprobe nvidia` to recover the rest. |
| SMN write returns no error but bits don't change on readback | This is the expected case if the strap mask covers the override too | Not a failure — it's the experimental answer. Run rollback (no-op) and document. |
| Retrain hangs the system | No TCP, BMC OK | BMC `power cycle`. Cold boot restores everything. |
| AER fatal error on root port | `dmesg` shows `pcieport ... AER: Multiple Fatal error received` | Same as MCE storm — reboot. AER may have already disabled the link via kernel error-recovery; rebooting clears the latched error state. |
| PCIE_LC_SPEED_CNTL2 wrote a bit that broke another port (collateral) | Other GPUs degrade or vanish | Rollback. If wrong SMN address was used, this is possible — emphasizes the importance of Step 4c sanity gates. |
| `setpci 60.l/64.l` race with another process | Garbage SMN address gets indexed; can write to an unintended NBIO register | Stop AMD-IOPM-UTIL and any other SMN tool before starting. Use `lsof /proc/bus/pci` to verify exclusive access. |

---

## Risk profile

**System under test:** 8x RTX 3090 production vLLM rig serving customer
traffic. TP=8 means a single dropped GPU kills the inference engine.

**Worst-case outcomes (ranked):**

1. **Multi-GPU fall-off.** If the SMN write somehow affects more than the test
   port (wrong SMN address, race condition during the index/data write,
   cross-port HW autonomous speed-change cascading), multiple GPUs could drop.
   Mitigation: BMC reboot. Recovery time: ~3-5 min cold boot. **Probability:
   low** if SMN address verification (Step 4c) is followed.

2. **Single-GPU permanent loss for the session.** Test GPU drops, secondary bus
   reset doesn't recover, requires reboot. **Probability: low-moderate.**
   Recovery: BMC reboot. Acceptable cost in a maintenance window.

3. **Kernel MCE storm + reboot.** Probability: low. Recovery: BMC reboot, then
   audit `journalctl -k` for any cascaded subsystem trouble.

4. **No effect at all (expected outcome).** Override write succeeds, retrain
   returns Gen3, no errors. Cost: maintenance window time. Information value:
   high — definitively closes the last no-flash hypothesis.

**Permanent damage probability: effectively zero.** No write in this runbook
touches a fuse, an OTP register, or a PSP-firmware-controlled value. All
writes are either explicitly RW or HwInit (which means the next cold boot
restores them). There is no path from this runbook to a bricked board.

**Production impact if the experiment fails:** one maintenance window
(approximately 15-30 minutes including rollback and verification). Reboot if
worst-case. Customer-traffic impact: schedule the window during off-peak.

---

## Step 8 — Completion checklist

- [ ] Authorized by user (banandana)
- [ ] vLLM stopped
- [ ] Second SSH + BMC IPMI both reachable
- [ ] Step 1 prerequisites all pass
- [ ] Step 2 baseline snapshot captured and copied off-host
- [ ] Step 3 test target chosen and confirmed (single port, identified by BDF)
- [ ] Step 4c sanity gates all pass (GEN3_EN=1, GEN4_EN=0, no existing override)
- [ ] Step 4d operator confirms the values to be written before the read
- [ ] Step 5 outcome captured (LnkSta, dmesg, nvidia-smi)
- [ ] Step 6 rollback executed
- [ ] Post-rollback: `LnkSta` matches baseline, all 8 GPUs visible, no MCE
- [ ] vLLM restarted and a smoke-test request served
- [ ] Result documented in `docs/RIG_RUNBOOK_GEN4_OVERRIDE_RESULTS.md` (new file)
- [ ] If outcome was the surprise (Gen4 succeeded): **STOP**, do not extend to
      remaining 7 ports. Document, soak-test the single port for 24h under
      typical workload, escalate to user before any extension.

---

## Appendix A — Why the strong prior says this fails

Per `docs/PPR_REGISTER_NOTES.md` and AMD's published PCIe-LTSSM behavior:

- TS1/TS2 ordered sets carry a "supported data rates" identifier that is
  derived from the `LC_GEN*_EN_STRAP` bits — not from the override.
- The link partner (the GPU) sees only the rates the root port advertises.
  With `GEN4_EN_STRAP=0`, the GPU never gets to attempt Gen4 negotiation.
- Even if `LC_TARGET_LINK_SPEED_OVERRIDE` is honored at the LTSSM speed-change
  request layer, the actual speed change FSM cannot reach a rate that wasn't
  in the advertised rate set.
- AMD's amdgpu driver uses these override bits in scenarios where the strap
  is already 1 — i.e. for fine-grained runtime control among already-enabled
  rates, not for unlocking a strap-disabled rate.

The non-zero probability of success rests on the possibility that the strap
gates only TS advertisement and not the internal rate-change FSM, allowing
the override to bypass advertisement when both link partners already
agreed on a higher rate via some other path. This is what `LC_FORCE_EN_HW_SPEED_CHANGE`
might enable. The PPR text for this exact corner case was unavailable during
Phase 1.

If the experiment succeeds, the surprise is that the strap is a soft mask, not
a hard clamp. If it fails, the strap is a hard clamp and Phase 1's verdict
("structural cap, no userspace fix") is fully confirmed.

---

## Appendix B — What this runbook does NOT do

- Does not flash BIOS. (Hard user constraint.)
- Does not write to NVRAM / UEFI variables.
- Does not write to PSP / SMU.
- Does not modify APCB, FFS, or any persistent firmware data.
- Does not change `/dev/mem` directly — all SMN access goes via PCI cfg
  index/data on the AMD root bridge using `setpci`.
- Does not extend to multiple ports — the experiment is one-port-only by
  design, even if the first port's outcome is positive.
- Does not survive a reboot — all writes here are volatile; a cold boot
  restores everything.

---

*End of runbook. Authorization required to proceed.*
