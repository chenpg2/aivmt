# Integrating `aivmt_sp` into the xiaozhi-esp32 fork

This scaffold is the **additive SP layer**. To turn it into a buildable firmware:

## 1. Fork & clone the base
```bash
# fork 78/xiaozhi-esp32 on GitHub, then:
git clone --recursive https://github.com/<you>/xiaozhi-esp32.git
cd xiaozhi-esp32
```

## 2. Drop in our component
Copy `AIVMT/firmware/components/aivmt_sp/` into the fork's `components/` (or add as a submodule).
Append `AIVMT/firmware/sdkconfig.defaults.aivmt` content to the fork's `sdkconfig.defaults`.

## 3. Wire the hooks (see `main_patches/application_hooks.md`)
In the base `main/application.cc`, construct an `aivmt::SpSession`, pass `Hooks` bound to the
existing display/TTS/audio/protocol calls, and forward button + ASR/TTS events as `SpEvent`s.

## 4. Board + endpoint
- Select board profile `bread-compact-wifi`.
- Set the chat/OTA endpoint to the **self-hosted** server (local-only; no cloud fallback) in
  `aivmt::SpConfig` / Kconfig. (Server = `xiaozhi-esp32-server`, separate track.)

## 5. Build & flash (ESP-IDF)
```bash
idf.py set-target esp32s3
idf.py menuconfig        # select board, set server URL, enable PTT
idf.py build flash monitor -p /dev/cu.usbserial-1410
```

## 6. Rollback if needed
```bash
esptool --port /dev/cu.usbserial-1410 write_flash 0x0 ../AIVMT/../xiaozhi-s3-fullflash-backup-20260609.bin
```
