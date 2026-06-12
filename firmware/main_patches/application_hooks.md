# How to wire `aivmt_sp` into the base `main/application.cc`

The base firmware owns the audio loop, display, and protocol. We attach `SpSession` and forward
events. Pseudo-patch (adapt to the fork's exact API names):

```cpp
#include "sp_session.h"
#include "sp_ptt.h"

static aivmt::SpSession* g_sp = nullptr;

void Application::StartAivmt() {
  aivmt::SpSession::Hooks hooks;
  hooks.show_text       = [this](const char* t){ display_->SetChatMessage("system", t); };
  hooks.speak           = [this](const char* t){ /* enqueue TTS via protocol_ */ };
  hooks.start_listening = [this]{ /* open ASR / begin turn */ };
  hooks.stop_listening  = [this]{ /* close ASR / end turn */ };
  hooks.emit_encounter  = [this](const aivmt::SpTelemetry& tel, const char* meta){
      /* send transcript + telemetry to the local server (MCP/HTTP) */ };

  g_sp = new aivmt::SpSession(aivmt::DefaultSpConfig(), hooks);
  g_sp->Start();
}
```

Forward events from existing callbacks:
- Button (boot/touch) press/release  → `g_sp->OnEvent(kPttPress / kPttRelease)`
- ASR final result for a student turn → `g_sp->telemetry().OnStudentQuestion()`
- "next"/confirm UI                   → `kConsentGiven` / `kBriefDone` / `kNext`
- TTS-done after feedback             → `kFeedbackShown`

Notes:
- In `kEncounter`, gate ASR on push-to-talk (half-duplex) — do not listen while TTS plays.
- Keep transport **local-only** (`SpConfig.local_only`): no cloud fallback.
