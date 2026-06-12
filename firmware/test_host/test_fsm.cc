// Host-side unit test for the SpSession state machine — NO ESP-IDF / hardware needed.
// Compile & run: `make -C AIVMT/firmware/test_host test`
// This is the verifiable target for `/goal`: it prints "ALL TESTS PASS" when the
// transition table in sp_session.cc is fully implemented (currently RED — that is the goal).

#include <cstdio>

#include "sp_session.h"

using namespace aivmt;

static int g_failures = 0;

#define CHECK_STATE(sess, expected)                                                   \
  do {                                                                                \
    if ((sess).state() != (expected)) {                                              \
      fprintf(stderr, "FAIL (line %d): expected %s, got %s\n", __LINE__,             \
              ToString(expected), ToString((sess).state()));                          \
      ++g_failures;                                                                   \
    } else {                                                                          \
      fprintf(stderr, "ok: %s\n", ToString(expected));                                \
    }                                                                                 \
  } while (0)

static SpSession MakeSession() {
  SpSession::Hooks hooks;
  hooks.show_text = [](const char*) {};
  hooks.speak = [](const char*) {};
  hooks.start_listening = [] {};
  hooks.stop_listening = [] {};
  hooks.emit_encounter = [](const SpTelemetry&, const char*) {};
  return SpSession(DefaultSpConfig(), hooks);
}

int main() {
  // Happy path through the OSCE flow.
  {
    SpSession s = MakeSession();
    s.Start();                                CHECK_STATE(s, SpState::kConsent);
    s.OnEvent(SpEvent::kConsentGiven);        CHECK_STATE(s, SpState::kCaseBrief);
    s.OnEvent(SpEvent::kBriefDone);           CHECK_STATE(s, SpState::kEncounter);
    s.OnEvent(SpEvent::kProbeStart);          CHECK_STATE(s, SpState::kReasoningProbe);
    s.OnEvent(SpEvent::kProbeAnswered);       CHECK_STATE(s, SpState::kFeedback);
    s.OnEvent(SpEvent::kFeedbackShown);       CHECK_STATE(s, SpState::kEnded);
  }

  // Abort from mid-encounter goes to Aborted.
  {
    SpSession s = MakeSession();
    s.Start();
    s.OnEvent(SpEvent::kConsentGiven);
    s.OnEvent(SpEvent::kAbort);               CHECK_STATE(s, SpState::kAborted);
  }

  if (g_failures == 0) {
    fprintf(stderr, "ALL TESTS PASS\n");
    return 0;
  }
  fprintf(stderr, "%d CHECK(S) FAILED\n", g_failures);
  return 1;
}
