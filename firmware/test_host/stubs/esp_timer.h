#pragma once
// Host-build stub for ESP-IDF esp_timer (used only by firmware/test_host).
#include <cstdint>

static inline int64_t esp_timer_get_time(void) { return 0; }
