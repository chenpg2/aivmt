// Patient persona rendering is provided by the host firmware through the
// SpSession::Hooks::show_persona callback (see sp_session.h / application.cc).
// This translation unit is intentionally minimal so the component stays
// base-firmware-agnostic; the PatientPersona data struct lives in sp_persona.h.

namespace aivmt {

// No host-agnostic implementation needed here.

}  // namespace aivmt
