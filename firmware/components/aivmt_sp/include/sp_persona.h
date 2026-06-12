#pragma once
// Patient persona display: turns the device from a "generic assistant" into a
// visible "patient" (embodiment / H2). Rendering routes through the base OLED.

#include <string>

#include "sp_config.h"

namespace aivmt {

struct PatientPersona {
  std::string case_id;
  std::string display_label;  // e.g. "Patient: 58M, chest pain" / "患者:58岁男性 胸痛"
  Language language = Language::kEn;
};

// Render the patient identity + a short state line to the device display.
// Implementation calls the base firmware's display hook.
void RenderPersona(const PatientPersona& persona, const char* state_text);

}  // namespace aivmt
