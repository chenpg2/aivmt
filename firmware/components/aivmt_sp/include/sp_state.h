#pragma once
// Standardized-patient session states and events (the OSCE flow).

namespace aivmt {

enum class SpState {
  kIdle,
  kConsent,         // consent + de-identified participant code
  kCaseBrief,       // present the case stem to the student
  kEncounter,       // history-taking dialogue (push-to-talk turns)
  kReasoningProbe,  // "state your differential and why"
  kFeedback,        // render score + structured feedback
  kEnded,
  kAborted,
};

enum class SpEvent {
  kStart,
  kConsentGiven,
  kBriefDone,
  kPttPress,
  kPttRelease,
  kProbeStart,
  kProbeAnswered,
  kFeedbackShown,
  kNext,
  kAbort,
  kTimeout,
};

inline const char* ToString(SpState s) {
  switch (s) {
    case SpState::kIdle: return "Idle";
    case SpState::kConsent: return "Consent";
    case SpState::kCaseBrief: return "CaseBrief";
    case SpState::kEncounter: return "Encounter";
    case SpState::kReasoningProbe: return "ReasoningProbe";
    case SpState::kFeedback: return "Feedback";
    case SpState::kEnded: return "Ended";
    case SpState::kAborted: return "Aborted";
  }
  return "Unknown";
}

inline const char* ToString(SpEvent e) {
  switch (e) {
    case SpEvent::kStart: return "Start";
    case SpEvent::kConsentGiven: return "ConsentGiven";
    case SpEvent::kBriefDone: return "BriefDone";
    case SpEvent::kPttPress: return "PttPress";
    case SpEvent::kPttRelease: return "PttRelease";
    case SpEvent::kProbeStart: return "ProbeStart";
    case SpEvent::kProbeAnswered: return "ProbeAnswered";
    case SpEvent::kFeedbackShown: return "FeedbackShown";
    case SpEvent::kNext: return "Next";
    case SpEvent::kAbort: return "Abort";
    case SpEvent::kTimeout: return "Timeout";
  }
  return "Unknown";
}

}  // namespace aivmt
