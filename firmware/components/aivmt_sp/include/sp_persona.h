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

// NOTE: persona rendering is performed by the host firmware via
// SpSession::Hooks::show_persona (label + state line) — there is no
// host-agnostic render function in this component.

}  // namespace aivmt
