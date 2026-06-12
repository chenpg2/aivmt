#pragma once
// SpSession — orchestrates one standardized-patient OSCE session on top of the
// xiaozhi base Application. See ../../ARCHITECTURE.md for the state machine.

#include <functional>

#include "sp_config.h"
#include "sp_participant.h"
#include "sp_persona.h"
#include "sp_state.h"
#include "sp_telemetry.h"

namespace aivmt {

class SpSession {
 public:
  // Capabilities the host firmware provides (bound to base display/audio/protocol).
  struct Hooks {
    std::function<void(const char* text)> show_text;   // -> OLED
    std::function<void(const char* text)> speak;       // -> TTS (patient voice)
    std::function<void()> start_listening;             // open ASR / begin a turn
    std::function<void()> stop_listening;              // close ASR / end a turn
    // Export the finished encounter (transcript + telemetry) to the local server.
    std::function<void(const SpTelemetry& tel, const char* meta_json)> emit_encounter;
  };

  SpSession(const SpConfig& cfg, Hooks hooks);

  void Start();                 // -> Consent
  void OnEvent(SpEvent event);  // drive the state machine
  SpState state() const { return state_; }
  TelemetryRecorder& telemetry() { return telemetry_; }

 private:
  void Enter(SpState next);     // transition + per-state entry actions

  SpConfig cfg_;
  Hooks hooks_;
  SpState state_ = SpState::kIdle;
  PatientPersona persona_;
  ParticipantCode participant_;
  TelemetryRecorder telemetry_;
};

}  // namespace aivmt
