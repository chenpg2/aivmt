#include "sp_participant.h"

#include <cctype>

namespace aivmt {

bool ParticipantCode::Set(const std::string& code) {
  // De-identified only: short alphanumeric code (e.g. "P017"). Reject PII-like input.
  if (code.empty() || code.size() > 12) return false;
  for (char c : code) {
    if (!std::isalnum(static_cast<unsigned char>(c))) return false;
  }
  // TODO(goal:participant): optionally reject digit-runs that look like IDs/phones.
  code_ = code;
  return true;
}

}  // namespace aivmt
