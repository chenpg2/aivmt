#include "sp_telemetry.h"

#include "esp_timer.h"

namespace aivmt {

void TelemetryRecorder::Begin() {
  data_ = SpTelemetry{};
  data_.t_start_ms = esp_timer_get_time() / 1000;
}

void TelemetryRecorder::OnStudentQuestion() { ++data_.n_student_questions; }

void TelemetryRecorder::OnVoluntaryRepeat() { ++data_.n_voluntary_repeats; }

void TelemetryRecorder::End() { data_.t_end_ms = esp_timer_get_time() / 1000; }

}  // namespace aivmt
