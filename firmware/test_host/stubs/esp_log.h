#pragma once
// Host-build stub for ESP-IDF logging (used only by firmware/test_host).
#include <cstdio>

#define ESP_LOGE(tag, ...) do { fprintf(stderr, "[E][%s] ", tag); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define ESP_LOGW(tag, ...) do { fprintf(stderr, "[W][%s] ", tag); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define ESP_LOGI(tag, ...) do { fprintf(stderr, "[I][%s] ", tag); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
#define ESP_LOGD(tag, ...) do { fprintf(stderr, "[D][%s] ", tag); fprintf(stderr, __VA_ARGS__); fputc('\n', stderr); } while (0)
