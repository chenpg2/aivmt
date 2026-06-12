#pragma once
// Compile/run-time configuration for the AIVMT standardized-patient layer.

#include <string>

namespace aivmt {

enum class Language { kEn, kZh };  // English primary, Chinese supported

struct SpConfig {
  Language language = Language::kEn;  // English primary; set kZh for Chinese
  // Local-only transport (patient confidentiality): self-hosted server, no cloud fallback.
  std::string server_url = "ws://CHANGE_ME_LOCAL_SERVER:PORT/xiaozhi/v1/";
  bool local_only = true;
  std::string default_case_id = "chestpain_en_01";
  int ptt_gpio = -1;             // TODO: set to the board's button GPIO
  int encounter_timeout_s = 600; // safety timeout for a session
};

// Returns defaults (later overridable via Kconfig / NVS).
inline SpConfig DefaultSpConfig() { return SpConfig{}; }

}  // namespace aivmt
