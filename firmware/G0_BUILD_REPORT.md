# G0 Build Report — 2026-06-10

## Result: ✅ GREEN (esp32s3, hard-asserted)

| Item | Value |
|---|---|
| ESP-IDF | v5.5.2 (repo requires ≥5.4) |
| Target | **esp32s3** (asserted in sdkconfig AND verified from the binary header: image chip id = esp32s3) |
| Board | `CONFIG_BOARD_TYPE_BREAD_COMPACT_WIFI=y` (matches the physical device's SKU from its boot log) |
| App image | `xiaozhi-esp32/build/xiaozhi.bin` — 2,648,944 bytes; fits app slot 0x3f0000 with **36% free** |
| Flash layout | bootloader@0x0, partition-table@0x8000, otadata@0xd000, app@0x20000, assets@0x800000, 16MB — **matches the partition table dumped from the real device exactly** |
| aivmt_sp linked | ✅ `build/esp-idf/aivmt_sp/libaivmt_sp.a` (our SP layer compiles & links under IDF) |

## What this is / is not
- IS: upstream xiaozhi (git main) + our `aivmt_sp` component **compiled & linked**, built for our exact board+flash layout. Proves the toolchain, the integration, and our code under the real cross-compiler.
- IS NOT yet: the SP experience. **Hooks are NOT wired** — `SpSession` is dormant; flashed as-is, the device would behave like stock (newer) xiaozhi pointing at the default server.

## Failure modes caught & fixed during G0 (for the record)
1. First build silently targeted plain **esp32** (stale empty `build/` made `set-target` abort; a pipe masked the non-zero exit) → produced a wrong-chip image despite "green" logs. Fix: clean `build/` + `sdkconfig`, `set -o pipefail`, explicit asserts on target/board/binary-chip-id.
2. Two background agents quit prematurely ("monitoring armed"); replaced by a deterministic single-chain script.

## Next firmware steps (in order)
1. **Wire hooks** in `main/application.cc` per `main_patches/application_hooks.md` (instantiate SpSession, route button/ASR/TTS events) — then rebuild.
2. Point endpoint at the self-hosted server (no cloud fallback), per `sdkconfig.defaults.aivmt` TODOs.
3. **Flash (requires user approval)** — full 16MB backup exists for rollback: `xiaozhi-s3-fullflash-backup-20260609.bin`.
4. On-device QA: PTT echo check, OLED persona, offline encounter, bench WER.

Flash command (when approved):
```
python -m esptool --chip esp32s3 -b 460800 --before default_reset --after hard_reset write_flash \
  0x0 build/bootloader/bootloader.bin 0x8000 build/partition_table/partition-table.bin \
  0xd000 build/ota_data_initial.bin 0x20000 build/xiaozhi.bin 0x800000 build/generated_assets.bin
```
