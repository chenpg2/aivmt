# ESP-IDF component registration for the AIVMT standardized-patient layer.
idf_component_register(
    SRCS
        "sp_session.cc"
        "sp_persona.cc"
        "sp_telemetry.cc"
        "sp_ptt.cc"
        "sp_participant.cc"
    INCLUDE_DIRS
        "include"
    REQUIRES
        driver          # GPIO for push-to-talk
        esp_timer       # timestamps for telemetry
    # TODO: add base deps exposed by the xiaozhi fork as the hooks are wired
    #       (e.g. display / audio / protocol components).
)
