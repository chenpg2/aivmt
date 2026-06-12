#pragma once
// De-identified participant code (academic integrity + logging). NO PII on device.

#include <string>

namespace aivmt {

class ParticipantCode {
 public:
  // Set a de-identified code (e.g. "P017"); rejects anything resembling PII.
  bool Set(const std::string& code);
  const std::string& value() const { return code_; }
  bool valid() const { return !code_.empty(); }

 private:
  std::string code_;
};

}  // namespace aivmt
