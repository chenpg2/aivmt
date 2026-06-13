"""Tests for the path-A zh OB/GYN graded-transcript generator.

Properties asserted:
* deterministic for a fixed (case, seed);
* every PATIENT utterance is traceable to the case YAML (closed-vocabulary check),
  including: the chief complaint opens the encounter, and each hidden_info content
  appears ONLY after its triggering checklist item is asked;
* designed_quality is monotone non-decreasing in checklist coverage;
* generated transcripts are valid Transcript objects;
* round-trips through the data/eval_transcripts JSON serialization;
* provenance is the synthetic apparatus tag and the loader fails loud otherwise.
"""

from __future__ import annotations

import json

import pytest

from aivmt.evalset import (
    PROVENANCE,
    apparatus_tokens,
    build_eval_set,
    case_content_tokens,
    eval_transcript_to_dict,
    generate_for_case,
    load_eval_set,
    load_eval_transcript,
    load_obgyn_cases,
    trigger_item_id,
    write_eval_set,
)
from aivmt.evalset.dataset import OBGYN_CASE_FILES
from aivmt.evalset.generator import QUALITY_TIERS, designed_quality
from aivmt.evalset.grounding import DEFAULT_NONANSWER_ZH
from aivmt.schemas import Transcript, Turn

SEED = 42
PER_CASE = 14


def _cases():
    return load_obgyn_cases()


def test_loads_three_obgyn_cases() -> None:
    cases = _cases()
    assert len(cases) == len(OBGYN_CASE_FILES) == 3
    assert {c.case_id for c in cases} == {
        "obgyn_ectopic_zh_01", "obgyn_aub_zh_01", "obgyn_vaginitis_zh_01"
    }
    for c in cases:
        assert c.language == "zh"
        assert c.specialty == "obgyn"


def test_generator_is_deterministic_for_fixed_seed() -> None:
    case = _cases()[0]
    a = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
    b = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
    assert [g.transcript for g in a] == [g.transcript for g in b]
    assert [g.designed_quality for g in a] == [g.designed_quality for g in b]
    assert [g.covered_item_ids for g in a] == [g.covered_item_ids for g in b]


def test_generator_rejects_too_few_transcripts() -> None:
    case = _cases()[0]
    with pytest.raises(ValueError, match=">= 2"):
        generate_for_case(case, seed=SEED, n_transcripts=1)


def test_every_patient_utterance_is_in_case_vocabulary() -> None:
    """No invented clinical facts: each patient line is a verbatim case string
    (or the case's own default non-answer / synthetic apparatus reply)."""
    for case in _cases():
        vocab = case_content_tokens(case) | apparatus_tokens() | {DEFAULT_NONANSWER_ZH}
        dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
        for g in dataset:
            for turn in g.transcript.turns:
                if turn.speaker == "patient":
                    assert turn.text in vocab, (
                        f"out-of-case patient utterance in {g.transcript.encounter_id}: {turn.text!r}"
                    )


def test_chief_complaint_opens_every_encounter() -> None:
    for case in _cases():
        dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
        for g in dataset:
            patient_lines = [t.text for t in g.transcript.turns if t.speaker == "patient"]
            assert patient_lines, f"{g.transcript.encounter_id}: no patient turns"
            assert patient_lines[0] == case.chief_complaint


def test_hidden_info_appears_only_after_its_trigger_item() -> None:
    """A hidden_info content may appear in a transcript ONLY if the checklist item
    its trigger names is among the covered items (i.e. the student asked for it)."""
    for case in _cases():
        # Map hidden content -> the item_id that earns it.
        earned_by = {}
        for hi in case.hidden_info:
            item_id = trigger_item_id(hi.trigger)
            if item_id is not None:
                earned_by[hi.content] = item_id
        assert earned_by, f"{case.case_id}: no hidden_info trigger resolved to an item_id"

        dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
        for g in dataset:
            covered = set(g.covered_item_ids)
            for turn in g.transcript.turns:
                if turn.speaker == "patient" and turn.text in earned_by:
                    assert earned_by[turn.text] in covered, (
                        f"{g.transcript.encounter_id}: hidden content {turn.text!r} disclosed "
                        f"without covering its trigger item {earned_by[turn.text]!r}"
                    )


def test_designed_quality_is_monotone_in_coverage() -> None:
    case = _cases()[0]
    n_items = len(case.history_checklist)
    qualities = [designed_quality(n_items, frac) for frac in sorted(QUALITY_TIERS)]
    assert qualities == sorted(qualities), f"non-monotone quality ladder: {qualities}"
    # And strictly spans low -> high (zero coverage to full coverage).
    assert qualities[0] == pytest.approx(0.0)
    assert qualities[-1] == pytest.approx(1.0)


def test_more_covered_items_never_lowers_quality_across_dataset() -> None:
    """Across the generated set, higher coverage count never yields lower quality."""
    for case in _cases():
        dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
        by_cov = sorted(dataset, key=lambda g: len(g.covered_item_ids))
        for lo, hi in zip(by_cov, by_cov[1:]):
            assert lo.designed_quality <= hi.designed_quality + 1e-9


def test_transcripts_are_valid_transcript_objects() -> None:
    case = _cases()[0]
    dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
    for g in dataset:
        tx = g.transcript
        assert isinstance(tx, Transcript)
        assert tx.language == "zh"
        assert tx.case_id == case.case_id
        assert tx.encounter_id.startswith(f"eval_{case.case_id}_")
        assert all(isinstance(t, Turn) and t.speaker in ("student", "patient") for t in tx.turns)
        assert tx.turns[-1].speaker in ("student", "patient")


def test_full_eval_set_has_expected_size_and_stable_ids() -> None:
    cases = _cases()
    dataset = build_eval_set(cases, seed=SEED, per_case=PER_CASE)
    assert len(dataset) == PER_CASE * len(cases) == 42
    ids = [g.transcript.encounter_id for g in dataset]
    assert len(set(ids)) == len(ids), "encounter_ids must be unique"
    # quality is diverse: spans low and high.
    qualities = [g.designed_quality for g in dataset]
    assert min(qualities) == pytest.approx(0.0)
    assert max(qualities) == pytest.approx(1.0)


def test_serialization_round_trip(tmp_path) -> None:
    case = _cases()[0]
    dataset = generate_for_case(case, seed=SEED, n_transcripts=PER_CASE)
    keys_dir = tmp_path / "keys"
    paths = write_eval_set(dataset, tmp_path, keys_dir=keys_dir)
    assert len(paths) == PER_CASE

    # BLINDING: the served transcript file is tagged synthetic but carries NO answer key —
    # designed_quality / covered_item_ids live only in the non-served key sidecar, so a rater
    # cannot de-blind by opening the transcript on disk.
    raw = json.loads(paths[0].read_text(encoding="utf-8"))
    assert raw["provenance"] == PROVENANCE
    assert "designed_quality" not in raw and "covered_item_ids" not in raw
    key = json.loads((keys_dir / f"{raw['encounter_id']}.json").read_text(encoding="utf-8"))
    assert "designed_quality" in key and "covered_item_ids" in key

    loaded = load_eval_set(tmp_path, keys_dir=keys_dir)
    assert len(loaded) == PER_CASE
    # Sorted-by-filename load matches sorted-by-id generation.
    by_id = {g.transcript.encounter_id: g for g in dataset}
    for tx, quality in loaded:
        original = by_id[tx.encounter_id]
        assert tx.turns == original.transcript.turns
        assert quality == pytest.approx(original.designed_quality)


def test_loader_rejects_non_synthetic_provenance(tmp_path) -> None:
    case = _cases()[0]
    g = generate_for_case(case, seed=SEED, n_transcripts=2)[0]
    record = eval_transcript_to_dict(g)
    record["provenance"] = "real"  # must be hard-refused
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="provenance"):
        load_eval_transcript(path)
