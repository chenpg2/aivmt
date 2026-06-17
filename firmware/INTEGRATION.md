# Integrating `aivmt_sp` into a xiaozhi-esp32 checkout

Our firmware is the additive **`aivmt_sp`** layer (this repo) applied to the upstream
[`78/xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32) base — we do not redistribute the base.
`$AIVMT` below = your clone of this repo.

## 1. Clone the upstream base
```bash
git clone --recursive https://github.com/78/xiaozhi-esp32.git
cd xiaozhi-esp32
```

## 2. Drop in our component
```bash
cp -r "$AIVMT/firmware/components/aivmt_sp" components/
```

## 3. Apply our integration patch (one shot)
Wires the SP layer into `main/application.cc`, registers the component in `main/CMakeLists.txt`, and
adds the `CONFIG_AIVMT_*` defaults to `sdkconfig.defaults`:
```bash
git apply "$AIVMT/firmware/main_patches/application.integration.patch"
```
The patch was generated against upstream near commit `8755a65`. If upstream has drifted and it does
not apply cleanly to `application.cc`, wire the hooks by hand following
[`main_patches/application_hooks.md`](main_patches/application_hooks.md): construct an
`aivmt::SpSession`, bind `Hooks` to the existing display/TTS/audio/protocol calls, and forward
button + ASR/TTS events as `SpEvent`s.

## 4. Board + endpoint
```bash
idf.py set-target esp32s3
idf.py menuconfig
#   board profile : bread-compact-wifi
#   CONFIG_AIVMT_ENCOUNTER_POST_URL = http://<SERVER_LAN_IP>:8003/aivmt/encounter   (local-only; no cloud fallback)
#   enable push-to-talk (BOOT / GPIO0)
```

## 5. Build & flash
```bash
idf.py build flash monitor -p /dev/cu.usbserial-XXXX   # your serial port (macOS example)
```
On the device: **short BOOT click = talk** (VAD, no wake word), **1-second long-press = export** the
encounter to the server. Full flash + on-device QA: [`FLASH_AND_QA.md`](FLASH_AND_QA.md).

## 6. Rollback if needed
Restore the device to the known-good full-flash image (kept outside the repo; `*.bin` is git-ignored):
```bash
esptool --port /dev/cu.usbserial-XXXX write_flash 0x0 xiaozhi-s3-fullflash-backup-20260609.bin
```
