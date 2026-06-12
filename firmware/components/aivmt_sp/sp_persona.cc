#include "sp_persona.h"

#include "esp_log.h"

namespace aivmt {

static const char* TAG = "AIVMT.Persona";

void RenderPersona(const PatientPersona& persona, const char* state_text) {
  // TODO(goal:persona): route to the base firmware's display API (OLED/LVGL).
  // Show persona.display_label as the "patient" identity + state_text as the status line.
  ESP_LOGI(TAG, "persona=%s state=%s", persona.display_label.c_str(),
           state_text ? state_text : "");
}

}  // namespace aivmt
