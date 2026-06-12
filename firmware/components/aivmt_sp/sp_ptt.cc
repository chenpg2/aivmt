#include "sp_ptt.h"

#include <utility>

#include "esp_log.h"

namespace aivmt {

static const char* TAG = "AIVMT.PTT";

PushToTalk::PushToTalk(int gpio) : gpio_(gpio) {}

void PushToTalk::Init() {
  // TODO(goal:ptt): configure gpio_ as input w/ pull, install ISR + debounce,
  // and call handler_(true) on press / handler_(false) on release.
  ESP_LOGI(TAG, "PushToTalk init gpio=%d", gpio_);
}

void PushToTalk::SetHandler(Handler h) { handler_ = std::move(h); }

}  // namespace aivmt
