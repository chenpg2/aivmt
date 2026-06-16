import json
import os
import re
import time

from aiohttp import web

from core.api.base_handler import BaseHandler

# Where finished standardized-patient encounters are archived (local-only; no cloud).
# Override with env AIVMT_ENCOUNTER_DIR; defaults to a folder under the server data dir.
_DEFAULT_DIR = os.path.join("data", "aivmt_encounters")
# A participant code is a short de-identified token; reject anything that is not a
# safe slug so it can never escape the archive directory (path-traversal guard).
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_REQUIRED = ("participant_code", "case_id", "transcript")


class AivmtHandler(BaseHandler):
    """Receives a finished AIVMT SP encounter from the device and archives it locally.

    The device POSTs {participant_code, case_id, telemetry, transcript[], meta} to
    ``/aivmt/encounter``. We validate, then write ONE JSON file per encounter under the
    local archive dir, keyed by participant_code. Nothing is sent to any cloud; the
    scoring pipeline reads these files directly. Fail-loud on malformed input (4xx),
    never 500 on a bad body.
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.archive_dir = os.environ.get("AIVMT_ENCOUNTER_DIR", _DEFAULT_DIR)

    def _bad(self, message: str):
        response = web.json_response({"success": False, "message": message}, status=400)
        self._add_cors_headers(response)
        return response

    async def handle_post(self, request):
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return self._bad("request body must be valid JSON")
        if not isinstance(body, dict):
            return self._bad("request body must be a JSON object")

        for field in _REQUIRED:
            if field not in body:
                return self._bad(f"missing required field: {field}")

        participant = str(body["participant_code"]).strip()
        case_id = str(body["case_id"]).strip()
        if not _SAFE_TOKEN.match(participant):
            return self._bad("participant_code must be a 1-32 char [A-Za-z0-9_-] token")
        if not _SAFE_TOKEN.match(case_id):
            return self._bad("case_id must be a 1-32 char [A-Za-z0-9_-] token")
        transcript = body["transcript"]
        if not isinstance(transcript, list) or not transcript:
            return self._bad("transcript must be a non-empty list of {role, text}")
        for turn in transcript:
            if not isinstance(turn, dict) or "role" not in turn or "text" not in turn:
                return self._bad("each transcript turn must have 'role' and 'text'")

        record = {
            "participant_code": participant,
            "case_id": case_id,
            "telemetry": body.get("telemetry", {}),
            "transcript": transcript,
            "meta": body.get("meta", {}),
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

        os.makedirs(self.archive_dir, exist_ok=True)
        # filename is safe by construction (both tokens validated above)
        fname = f"{participant}__{case_id}__{int(time.time())}.json"
        path = os.path.join(self.archive_dir, fname)
        # atomic write: temp file + replace, so a partial write is never archived
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError as exc:
            self.logger.error(f"AIVMT: failed to archive encounter: {exc}")
            response = web.json_response(
                {"success": False, "message": "server failed to archive encounter"},
                status=500,
            )
            self._add_cors_headers(response)
            return response

        self.logger.info(
            f"AIVMT: archived encounter participant={participant} case={case_id} "
            f"turns={len(transcript)} -> {path}"
        )
        response = web.json_response(
            {"success": True, "stored": fname, "turns": len(transcript)}
        )
        self._add_cors_headers(response)
        return response
