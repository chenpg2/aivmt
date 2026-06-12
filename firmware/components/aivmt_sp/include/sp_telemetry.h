#pragma once
// Behavioral telemetry for the H2 engagement composite (time-on-task,
// # student questions, # voluntary repeats). Emitted with the transcript.

#include <cstdint>

namespace aivmt {

struct SpTelemetry {
  uint32_t n_student_questions = 0;
  uint32_t n_voluntary_repeats = 0;
  int64_t t_start_ms = 0;
  int64_t t_end_ms = 0;

  double DurationSeconds() const {
    return t_end_ms > t_start_ms ? (t_end_ms - t_start_ms) / 1000.0 : 0.0;
  }
};

class TelemetryRecorder {
 public:
  void Begin();              // stamp t_start_ms (esp_timer)
  void OnStudentQuestion();  // increment on each student turn
  void OnVoluntaryRepeat();  // increment when the student replays/repeats
  void End();                // stamp t_end_ms
  const SpTelemetry& data() const { return data_; }

 private:
  SpTelemetry data_;
};

}  // namespace aivmt
