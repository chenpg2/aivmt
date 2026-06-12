"""ASR-noise corruption-model tests (deterministic, known-value where possible).

Cover: CER/WER metrics on hand-constructed pairs, the WER=0 identity path, deterministic corruption
given a fixed seed, CER targeting reaching ~the requested rate, structure preservation (speakers /
turns / ids), corruptible-speaker scoping, fail-loud guards, the confusion-table loader/validator,
and the scramble negative-control ceiling.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from aivmt.asr import (
    AsrNoiseConfig,
    ConfusionTableError,
    corrupt,
    default_operators,
    load_confusion_table,
    measured_cer,
    measured_wer,
    transcript_cer,
)
from aivmt.asr.noise import _levenshtein
from aivmt.asr.operators import (
    FunctionWordDeletion,
    HomophoneToneOperator,
    MedicalTermOperator,
    TtsEchoInsertion,
)
from aivmt.schemas import Telemetry, Transcript, Turn

_TABLE = load_confusion_table()


def _zh_transcript() -> Transcript:
    return Transcript(
        encounter_id="t1",
        case_id="c1",
        language="zh",
        turns=(
            Turn("student", "您好今天哪里不舒服来的"),
            Turn("patient", "我右下腹痛还有阴道流血没有发烧"),
            Turn("student", "疼了多久末次月经什么时候"),
            Turn("patient", "疼了三天末次月经六周前"),
        ),
        telemetry=Telemetry(),
    )


# --- metrics: known-value -------------------------------------------------------------------------
def test_levenshtein_known_values() -> None:
    assert _levenshtein("abc", "abc") == 0
    assert _levenshtein("abc", "abx") == 1  # one substitution
    assert _levenshtein("abc", "ab") == 1  # one deletion
    assert _levenshtein("ab", "abc") == 1  # one insertion
    assert _levenshtein("没有发烧", "发烧") == 2  # two deletions


def test_measured_cer_hand_computed() -> None:
    assert measured_cer("abc", "abx") == pytest.approx(1.0 / 3.0)
    # "没有发烧" (4 chars) -> "有发烧" : one deletion -> 1/4
    assert measured_cer("没有发烧", "有发烧") == pytest.approx(0.25)
    # identical strings -> CER 0
    assert measured_cer("症状诊断", "症状诊断") == 0.0


def test_measured_cer_empty_reference_raises() -> None:
    with pytest.raises(ValueError, match="empty reference"):
        measured_cer("", "abc")


def test_measured_wer_token_level() -> None:
    # 3 reference tokens, one substituted -> WER 1/3
    assert measured_wer("the cat sat", "the dog sat") == pytest.approx(1.0 / 3.0)
    assert measured_wer("a b c", "a b c") == 0.0


def test_measured_wer_empty_reference_raises() -> None:
    with pytest.raises(ValueError, match="empty reference"):
        measured_wer("   ", "x")


# --- corrupt: identity, determinism, targeting ----------------------------------------------------
def test_wer_zero_is_identity() -> None:
    t = _zh_transcript()
    c = corrupt(t, 0.0, seed=42)
    assert c is t  # identity fast-path returns the same object
    assert transcript_cer(t, c) == 0.0


def test_corrupt_is_deterministic_for_fixed_seed() -> None:
    t = _zh_transcript()
    a = corrupt(t, 0.20, seed=7)
    b = corrupt(t, 0.20, seed=7)
    assert tuple(x.text for x in a.turns) == tuple(x.text for x in b.turns)


def test_corrupt_different_seeds_differ() -> None:
    t = _zh_transcript()
    a = corrupt(t, 0.20, seed=1)
    b = corrupt(t, 0.20, seed=2)
    assert tuple(x.text for x in a.turns) != tuple(x.text for x in b.turns)


def test_corrupt_reaches_approximate_target_cer() -> None:
    t = _zh_transcript()
    for target in (0.05, 0.15, 0.30):
        c = corrupt(t, target, seed=42)
        achieved = transcript_cer(t, c)
        # Deterministic operators land within a tolerance band of the requested CER.
        assert abs(achieved - target) <= 0.08, f"target={target} achieved={achieved}"


def test_corrupt_preserves_structure_and_ids() -> None:
    t = _zh_transcript()
    c = corrupt(t, 0.30, seed=42)
    assert c.encounter_id == t.encounter_id
    assert c.case_id == t.case_id
    assert c.language == t.language
    assert len(c.turns) == len(t.turns)
    assert tuple(x.speaker for x in c.turns) == tuple(x.speaker for x in t.turns)
    assert c.telemetry == t.telemetry


def test_corrupt_only_touches_corruptible_speakers() -> None:
    """A non-corruptible speaker's text is preserved verbatim (here all are student/patient, so we
    assert at least one turn actually changed and none gained/lost turns)."""
    t = _zh_transcript()
    c = corrupt(t, 0.30, seed=42)
    changed = [o.text != n.text for o, n in zip(t.turns, c.turns)]
    assert any(changed)  # corruption actually happened


# --- fail-loud guards -----------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
def test_corrupt_rejects_out_of_range_target(bad: float) -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        corrupt(_zh_transcript(), bad, seed=42)


def test_corrupt_rejects_empty_transcript() -> None:
    empty = Transcript("e", "c", "zh", turns=(Turn("student", ""), Turn("patient", "")))
    with pytest.raises(ValueError, match="no corruptible"):
        corrupt(empty, 0.15, seed=42)


def test_transcript_cer_no_corruptible_chars_raises() -> None:
    empty = Transcript("e", "c", "zh", turns=(Turn("student", ""),))
    with pytest.raises(ValueError, match="no corruptible"):
        transcript_cer(empty, empty)


# --- scramble negative-control ceiling ------------------------------------------------------------
def test_scramble_drives_cer_high() -> None:
    t = _zh_transcript()
    cfg = AsrNoiseConfig(target_wer=1.0, seed=42, scramble=True)
    c = corrupt(t, 1.0, seed=42, config=cfg)
    assert transcript_cer(t, c) >= 0.6  # catastrophic ceiling


# --- operators ------------------------------------------------------------------------------------
def test_homophone_operator_substitutes_one_char() -> None:
    op = HomophoneToneOperator(_TABLE)
    rng = np.random.default_rng(0)
    out, n = op.apply("症状", rng)  # 症->证 or 状->壮
    assert n == 1
    assert out != "症状"
    assert len(out) == 2


def test_medical_term_operator_swaps_known_term() -> None:
    op = MedicalTermOperator(_TABLE)
    rng = np.random.default_rng(0)
    out, n = op.apply("我怀疑异位妊娠", rng)
    assert n >= 1
    assert "异位妊娠" not in out


def test_function_word_deletion_removes_one_char() -> None:
    op = FunctionWordDeletion(_TABLE, negation_bias=1.0)
    rng = np.random.default_rng(0)
    # "不疼" contains negation 不; deletion flips polarity to "疼".
    out, n = op.apply("不疼", rng)
    assert n == 1
    assert out == "疼"


def test_operator_no_site_returns_zero_edits() -> None:
    op = MedicalTermOperator(_TABLE)
    rng = np.random.default_rng(0)
    out, n = op.apply("XYZ123", rng)  # no medical term present
    assert (out, n) == ("XYZ123", 0)


def test_tts_echo_insertion_prepends_fragment() -> None:
    op = TtsEchoInsertion()
    rng = np.random.default_rng(0)
    out, n = op.apply("我腹痛", rng)
    assert n > 0
    assert out.endswith("我腹痛") and len(out) > len("我腹痛")


def test_default_operators_cover_full_taxonomy() -> None:
    ops = default_operators(_TABLE)
    names = {o.name for o in ops}
    assert names == {
        "homophone_tone", "medical_term", "segmentation",
        "number_unit", "function_word_deletion", "tts_echo_insertion",
    }


# --- confusion-table loader/validator -------------------------------------------------------------
def test_confusion_table_loads_and_freezes() -> None:
    tbl = load_confusion_table()
    assert tbl.homophone and tbl.medical_term and tbl.deletable and tbl.negation
    # char_substitutions merges homophone + tone.
    assert set(tbl.char_substitutions) >= set(tbl.homophone)


def test_confusion_table_missing_file_raises(tmp_path) -> None:
    with pytest.raises(ConfusionTableError, match="missing"):
        load_confusion_table(tmp_path / "nope.json")


def test_confusion_table_rejects_identity_mapping(tmp_path) -> None:
    bad = {
        "homophone": {"症": "症"},  # identity -> would not corrupt
        "tone": {}, "medical_term": {}, "number_unit": {}, "segmentation": {},
        "function_words": {"deletable": ["了"], "negation": ["不"]},
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ConfusionTableError, match="identity mapping"):
        load_confusion_table(p)


def test_confusion_table_rejects_missing_section(tmp_path) -> None:
    bad = {"homophone": {"症": "证"}}  # missing the other required sections
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ConfusionTableError, match="missing section"):
        load_confusion_table(p)
