#include "sp_session.h"

#include <utility>

#include "esp_log.h"
#include "sp_persona.h"

namespace aivmt {

static const char* TAG = "AIVMT.SpSession";

// Pick a localized string (zh primary, en supported).
static const char* Pick(Language lang, const char* zh, const char* en) {
  return lang == Language::kZh ? zh : en;
}

SpSession::SpSession(const SpConfig& cfg, Hooks hooks)
    : cfg_(cfg), hooks_(std::move(hooks)) {
  persona_.case_id = cfg_.default_case_id;
  persona_.language = cfg_.language;
  persona_.display_label = Pick(cfg_.language, "患者", "Patient");
  participant_.Set(cfg_.participant_code);  // non-empty default so encounter export validates
}

void SpSession::Start() { Enter(SpState::kConsent); }

void SpSession::Enter(SpState next) {
  state_ = next;
  ESP_LOGI(TAG, "enter %s", ToString(state_));

  switch (state_) {
    case SpState::kConsent:
      if (hooks_.show_text) {
        hooks_.show_text(Pick(cfg_.language,
                              "请输入参与者编号并确认知情同意。",
                              "Enter participant code and confirm consent."));
      }
      break;

    case SpState::kCaseBrief:
      if (hooks_.show_text) hooks_.show_text(persona_.display_label.c_str());
      if (hooks_.speak) {
        hooks_.speak(Pick(cfg_.language,
                          "下面开始问诊,请采集病史。",
                          "The encounter begins; please take the history."));
      }
      break;

    case SpState::kEncounter:
      telemetry_.Begin();
      if (hooks_.show_persona) {
        hooks_.show_persona(persona_.display_label.c_str(),
                            Pick(cfg_.language, "问诊中", "Encounter"));
      }
      // Half-duplex: wait for push-to-talk; do not auto-listen (no-AEC mitigation).
      break;

    case SpState::kReasoningProbe:
      if (hooks_.speak) {
        hooks_.speak(Pick(cfg_.language,
                          "请说出你的鉴别诊断及理由。",
                          "Please state your differential diagnosis and your reasoning."));
      }
      break;

    case SpState::kFeedback:
      // Score + structured feedback are produced server-side, then rendered here.
      if (hooks_.show_persona) {
        hooks_.show_persona(persona_.display_label.c_str(),
                            Pick(cfg_.language, "反馈", "Feedback"));
      }
      break;

    case SpState::kEnded:
      telemetry_.End();
      if (hooks_.emit_encounter) {
        hooks_.emit_encounter(telemetry_.data(), "{\"status\":\"ended\"}");
      }
      break;

    case SpState::kAborted:
      telemetry_.End();
      if (hooks_.show_text) {
        hooks_.show_text(Pick(cfg_.language, "会话已中止。", "Session aborted."));
      }
      break;

    case SpState::kIdle:
      break;
  }
}

void SpSession::OnEvent(SpEvent event) {
  ESP_LOGI(TAG, "event %s in %s", ToString(event), ToString(state_));

  // Abort is valid from any state.
  if (event == SpEvent::kAbort) {
    Enter(SpState::kAborted);
    return;
  }

  switch (state_) {
    case SpState::kConsent:
      if (event == SpEvent::kConsentGiven) Enter(SpState::kCaseBrief);
      break;

    case SpState::kCaseBrief:
      if (event == SpEvent::kBriefDone) Enter(SpState::kEncounter);
      break;

    case SpState::kEncounter:
      switch (event) {
        case SpEvent::kPttPress:
          if (hooks_.start_listening) hooks_.start_listening();
          break;
        case SpEvent::kPttRelease:
          if (hooks_.stop_listening) hooks_.stop_listening();
          telemetry_.OnStudentQuestion();
          break;
        case SpEvent::kProbeStart:
          Enter(SpState::kReasoningProbe);
          break;
        default:
          break;
      }
      break;

    case SpState::kReasoningProbe:
      if (event == SpEvent::kProbeAnswered) Enter(SpState::kFeedback);
      break;

    case SpState::kFeedback:
      if (event == SpEvent::kFeedbackShown) Enter(SpState::kEnded);
      break;

    default:
      ESP_LOGW(TAG, "ignored event %s in %s", ToString(event), ToString(state_));
      break;
  }
}

}  // namespace aivmt
