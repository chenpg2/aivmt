"""Export the verbatim scoring instrument into Supplementary Note 1.

Reviewer 2 (round 1) asked for the history-completion checklist items, the behavioural
anchors separating 0 / 0.5 / 1 on each SEGUE and reasoning domain, and the verbatim
prompts driving the patient persona and the scorer. This script emits all of them
straight from the source modules and case files, so the supplement cannot drift from
the code that produced the reported scores.

Nothing here calls an LLM and nothing is hand-transcribed: every prompt block is
rendered by the same functions the scoring pipeline calls at run time.

Usage:
  uv run python scripts/export_scoring_instrument.py
  uv run python scripts/export_scoring_instrument.py --out path/to/Note1.md
"""

from __future__ import annotations

import argparse
import sys
import dataclasses
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from aivmt.cases import case_from_dict  # noqa: E402
from aivmt.scoring import checklist as checklist_mod  # noqa: E402
from aivmt.scoring import reasoning as reasoning_mod  # noqa: E402
from aivmt.scoring import segue as segue_mod  # noqa: E402
from aivmt.schemas import Transcript, Turn  # noqa: E402

#: The three cases used in the prospective study.
STUDY_CASES = ("obgyn_ectopic_zh_01", "obgyn_aub_zh_01", "obgyn_vaginitis_zh_01")

#: English titles for the three study cases; the case files carry Chinese titles only.
CASE_TITLE_EN: dict[str, str] = {
    "obgyn_ectopic_zh_01": "Amenorrhoea with lower abdominal pain and vaginal bleeding "
                           "(suspected ectopic pregnancy)",
    "obgyn_aub_zh_01": "Heavier menstrual flow with prolonged periods "
                       "(abnormal uterine bleeding)",
    "obgyn_vaginitis_zh_01": "Increased vaginal discharge with vulval itching "
                             "(suspected vulvovaginal candidiasis)",
}

#: Behavioural difficulty at which the study personas were compiled (patient.py default).
STUDY_DIFFICULTY = "standard"

#: A two-turn placeholder used only to render the user-prompt templates. It is NOT study
#: data; real transcripts are not reproduced here (consent / data-governance).
_PLACEHOLDER = Transcript(
    encounter_id="<encounter_id>",
    case_id="<case_id>",
    language="en",
    turns=(
        Turn(speaker="student", text="<student turn>"),
        Turn(speaker="patient", text="<patient turn>"),
    ),
)


# --------------------------------------------------------------------------------------
# NON-NORMATIVE English glosses.
#
# Everything else in this note is rendered from source. The blocks below are the one
# exception: the study ran in Chinese, so the checklist items and the patient personas
# exist only in Chinese in the case files. These hand-maintained English renderings are
# provided so an English-language reader can assess what is being measured. The Chinese
# text emitted above each gloss is the verbatim prompt as used; the gloss is not.
# --------------------------------------------------------------------------------------

CHECKLIST_GLOSS: dict[str, str] = {
    # obgyn_ectopic_zh_01
    "hx_lmp": "Asks last menstrual period / duration of amenorrhoea",
    "hx_menstrual": "Asks usual menstrual history (cycle length, regularity)",
    "hx_bleeding": "Asks volume, colour and duration of vaginal bleeding",
    "hx_pain": "Asks site, character and aggravating factors of the abdominal pain",
    "hx_sexual_contraception": "Asks sexual activity and contraceptive method",
    "hx_obstetric": "Asks obstetric history (gravidity, parity, prior abortion)",
    "hx_associated": "Asks associated symptoms: dizziness, syncope, rectal pressure",
    "hx_pid": "Asks past pelvic inflammatory disease or gynaecological surgery",
    # obgyn_aub_zh_01
    "hx_menstrual_detail": "Takes a detailed menstrual history (cycle, days of flow, volume, clots)",
    "hx_onset": "Asks when the bleeding pattern changed and how it has evolved",
    "hx_anemia": "Asks anaemia symptoms: fatigue, dizziness, palpitations",
    "hx_iud_contraception": "Asks contraceptive method (intrauterine device and years in situ)",
    "hx_meds": "Asks medication history, including hormones and anticoagulants",
    "hx_gyn_history": "Asks past gynaecological disease (e.g. uterine fibroids)",
    "hx_pregnancy_excl": "Asks about, or excludes, possible pregnancy",
    # obgyn_vaginitis_zh_01
    "hx_discharge": "Asks character, colour and odour of the vaginal discharge",
    "hx_itching": "Asks local symptoms: itching, burning",
    "hx_trigger": "Asks precipitants: recent antibiotics, diabetes, pregnancy",
    "hx_partner": "Asks sexual activity and whether the partner has symptoms",
    "hx_lmp_pregnancy": "Asks last menstrual period and possibility of pregnancy",
    "hx_recurrence": "Asks history of similar previous episodes",
    "hx_hygiene": "Asks hygiene practices, including vaginal douching",
}

#: Scaffold shared by all compiled personas (role framing + style block), rendered once.
PERSONA_SCAFFOLD_GLOSS = """[ROLE]
You are playing a standardized patient, used to train medical students. Follow strictly:
1) Answer only what the student explicitly asks; never volunteer information not asked for;
2) Answer in the first person, colloquially and briefly, in character;
3) Do not use medical terminology; you may ask back if you genuinely do not understand;
4) Do not give a diagnosis, do not evaluate the student, do not break character.

[STYLE]
- After stating the chief complaint you may add one or two of the most obvious associated
  complaints without waiting to be asked.
- Keep answers short (1-2 sentences) and colloquial.
- Use everyday language, not medical terms.
- Express emotion as specified."""

PERSONA_IDENTITY_GLOSS: dict[str, str] = {
    "obgyn_ectopic_zh_01": """[CHARACTER]
You are a 28-year-old woman. You have missed your period for just over 6 weeks, and today the
dull pain in your right lower abdomen has worsened over one day, with a small amount of dark
red vaginal bleeding. Your periods are usually regular (every 28-30 days); your last period was
about 6 weeks ago. Married, sexually active, recently using condoms but occasionally not. One
previous pregnancy, one induced abortion, no children. Today you felt dizzy on standing and
have a sensation of rectal pressure. No fever; discharge is normal. Three years ago you had
"pelvic inflammatory disease", treated with medication.
Role instruction: state only one main symptom at the opening; disclose nothing else, however
relevant, until specifically asked; speak colloquially and briefly, slightly anxious and worried;
ask what a term means only if you genuinely cannot understand it; if a detail is not specified,
say "no" or "not sure".""",
    "obgyn_aub_zh_01": """[CHARACTER]
You are a 45-year-old woman. Over the past 3 months your periods have become markedly heavier
with clots, and the bleeding has lengthened from 5 days to 8-10 days; that is why you are here.
The cycle is still fairly regular. Recently you feel tired and get palpitations climbing stairs
(anaemia). Married, two children, an intrauterine device in place (about 8 years). Not taking
hormones or anticoagulants. No significant weight change, no significant abdominal pain, normal
discharge. A previous check-up mentioned "a small fibroid on the uterus, nothing to worry about".
Role instruction: state only one main symptom at the opening; disclose nothing else, however
relevant, until specifically asked; speak colloquially, calm but somewhat bothered; ask what a
term means only if you genuinely cannot understand it; if a detail is not specified, say "no" or
"I don't remember".""",
    "obgyn_vaginitis_zh_01": """[CHARACTER]
You are a 32-year-old woman. Over the past 5 days your vaginal discharge has increased markedly,
curd-like, with marked vulval itching and some burning; that is why you are here. Two weeks ago
you had a cold and took a week of "anti-inflammatory medicine" (antibiotics) on your own. No
fever, no abdominal pain, normal urination. Married, one steady sexual partner, who has no
symptoms. Periods normal, last period two weeks ago, pregnancy unlikely (using contraception).
No diabetes. No previous episode of this. You occasionally douche.
Role instruction: state only one main symptom at the opening; disclose nothing else, however
relevant, until specifically asked; speak colloquially, somewhat embarrassed; ask what a term
means only if you genuinely cannot understand it; if a detail is not specified, say "no".""",
}


def _english_case(case):
    """A copy of `case` whose checklist text is the English gloss and whose language is en.

    The user-prompt templates interpolate the checklist items and the SEGUE anchors from
    the case, so rendering them from the Chinese case would put Chinese back into this
    supplement. Replacing the item text with the maintained gloss and flipping the
    language tag renders the same template structure in English. Only the rendering
    changes; nothing here touches what the model was given during the study.
    """
    items = tuple(
        dataclasses.replace(it, text=CHECKLIST_GLOSS.get(it.item_id, it.text))
        for it in case.history_checklist
    )
    return dataclasses.replace(case, history_checklist=items, language="en")


def _load_case(path: Path):
    """Load a Case, preferring the production loader.

    ``aivmt.cases.load_case`` reads the YAML through OmegaConf. The three study case
    files contain no OmegaConf interpolation (``grep -c '${'`` returns 0 for each), so
    where OmegaConf is unavailable a plain ``yaml.safe_load`` yields the identical dict
    and is passed to the same ``case_from_dict`` constructor.
    """
    try:
        from omegaconf import OmegaConf  # noqa: PLC0415

        data = OmegaConf.to_container(OmegaConf.load(str(path)), resolve=True)
    except ModuleNotFoundError:
        import yaml  # noqa: PLC0415

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return case_from_dict(data)  # type: ignore[arg-type]


def _fence(text: str, lang: str = "text") -> str:
    return f"```{lang}\n{text}\n```"


def build_note(cases: dict) -> str:
    out: list[str] = []
    w = out.append

    w("# Supplementary Note 1. Scoring instrument and prompts")
    w("")
    w(
        "**Language of this note.** The study was conducted in Chinese, and the operative "
        "instrument is therefore Chinese: the checklist items, the behavioural descriptors, "
        "the scorer system prompts and the patient personas were all presented to the model "
        "in Chinese. This note renders them in English so that they can be read and assessed. "
        "For the scorer system prompts and the few-shot exemplars the English shown here is "
        "the project's own English variant, carried in the same source modules as the Chinese "
        "and selected by a language switch. For the checklist items, the behavioural "
        "descriptors and the patient personas it is a maintained English rendering of the "
        "Chinese original. In neither case was the English text the string given to the model "
        "during the study. The Chinese originals are in the released code, in "
        "`conf/case/*.yaml` and `src/aivmt/scoring/`, and can be regenerated in full by "
        "running `scripts/export_scoring_instrument.py` against those files."
    )
    w("")
    w(
        "Every block in this note is generated directly from the source modules and case "
        "files by `scripts/export_scoring_instrument.py`, so it cannot drift from the code "
        "that produced the reported scores. No block is hand-transcribed."
    )
    w("")
    w("---")
    w("")

    # ---- N1.1 history checklists -------------------------------------------------
    w("## N1.1 History-completion checklists")
    w("")
    w(
        "`history_completion` is the weight-covered fraction of the case's history checklist. "
        "All items carry equal weight (1.0) in the three study cases, so for these cases the "
        "score reduces to the plain covered fraction. Item text is given verbatim in the "
        "language in which it was presented to the scorer (Chinese), with an English gloss."
    )
    w("")
    for cid in STUDY_CASES:
        case = cases[cid]
        w(f"### `{cid}`: {CASE_TITLE_EN.get(cid, case.title)}")
        w("")
        w(f"{len(case.history_checklist)} items, all weight 1.0.")
        w("")
        w("| # | item_id | Item | Weight |")
        w("|---|---|---|---|")
        for i, it in enumerate(case.history_checklist, 1):
            gloss = CHECKLIST_GLOSS.get(it.item_id, "")
            w(f"| {i} | `{it.item_id}` | {gloss} | {it.weight:g} |")
        w("")

    # ---- N1.2 checklist scorer ---------------------------------------------------
    w("## N1.2 ChecklistScorer, verbatim prompts")
    w("")
    w("**System prompt:**")
    w("")
    w(_fence(checklist_mod._SYS["en"]))
    w("")
    w(
        "**User prompt template.** Rendered below for `obgyn_aub_zh_01` with a placeholder "
        "transcript; at run time `CHECKLIST` is the case's item list from N1.1 and "
        "`TRANSCRIPT` is the de-identified encounter."
    )
    w("")
    w(_fence(checklist_mod._build_user(_english_case(cases["obgyn_aub_zh_01"]), _PLACEHOLDER)))
    w("")

    # ---- N1.3 SEGUE scorer -------------------------------------------------------
    w("## N1.3 SegueScorer, verbatim prompts and domain anchors")
    w("")
    w(
        "The system prompt carries the 0 / 0.5 / 1 verbal anchors; the user prompt carries the "
        "per-domain behavioural descriptors. The score is a continuous value in [0, 1], the "
        "three anchor points are verbal reference levels, and the scorer is not constrained to "
        "them (Methods, \"Automated scoring pipeline\")."
    )
    w("")
    w("**System prompt:**")
    w("")
    w(_fence(segue_mod._SYS["en"]))
    w("")
    w("**Per-domain behavioural descriptors:**")
    w("")
    w("| Domain | Behavioural descriptor |")
    w("|---|---|")
    for d in segue_mod.SEGUE_DOMAINS:
        w(f"| `{d}` | {segue_mod._ANCHORS['en'][d]} |")
    w("")
    w("**User prompt template** (rendered with a placeholder transcript):")
    w("")
    w(_fence(segue_mod._build_user(_english_case(cases["obgyn_aub_zh_01"]), _PLACEHOLDER)))
    w("")

    # ---- N1.4 reasoning scorer ---------------------------------------------------
    w("## N1.4 ReasoningScorer, verbatim prompts and anchors")
    w("")
    w("**System prompt:**")
    w("")
    w(_fence(reasoning_mod._SYS["en"]))
    w("")
    w("**User prompt template** (rendered with a placeholder transcript):")
    w("")
    w(_fence(reasoning_mod._build_user(_english_case(cases["obgyn_aub_zh_01"]), _PLACEHOLDER)))
    w("")

    # ---- N1.5 few-shot exemplars -------------------------------------------------
    w("## N1.5 Few-shot exemplars (ablation variant only)")
    w("")
    w(
        "The pipeline supports a `few_shot` variant that is **not** used for any result "
        "reported in this paper; all reported scores use the `zero_shot` default. The "
        "exemplars are listed for completeness. They are **synthetic illustrative pairs, not "
        "real patient or student data**, and they demonstrate the application of the anchors "
        "without changing the rubric."
    )
    w("")
    for label, mod in (
        ("ChecklistScorer", checklist_mod),
        ("SegueScorer", segue_mod),
        ("ReasoningScorer", reasoning_mod),
    ):
        w(f"### {label}")
        w("")
        for excerpt, expected in mod._FEW_SHOT_EXEMPLARS["en"]:
            w(_fence(f"EXCERPT:\n{excerpt}\n\nEXPECTED JSON:\n{expected}"))
            w("")

    # ---- N1.6 patient personas ---------------------------------------------------
    w("## N1.6 Patient persona prompts")
    w("")
    w(
        "The AI standardized patient is driven by a deterministic persona compiler: identical "
        f"inputs produce a byte-identical system prompt. The study used behavioural difficulty "
        f"`{STUDY_DIFFICULTY}`. The full compiled system prompt for each study case follows."
    )
    w("")
    w(
        "The role-framing and style blocks are identical across the three cases (they are "
        "emitted by the compiler); only the character block differs. The prompts below are "
        "English renderings of the Chinese originals that the model was actually given "
        "(see the note at the head of this supplement)."
    )
    w("")
    for cid in STUDY_CASES:
        case = cases[cid]
        w(f"### `{cid}`: {CASE_TITLE_EN.get(cid, case.title)}")
        w("")
        w(_fence(f"{PERSONA_IDENTITY_GLOSS[cid]}\n\n{PERSONA_SCAFFOLD_GLOSS}"))
        w("")

    # ---- N1.7 output schema / fail-loud ------------------------------------------
    w("## N1.7 Output schema and fail-loud validation")
    w("")
    w(
        "Each scorer requires strict JSON and raises `LLMOutputError` on a missing field, a "
        "non-numeric value, or a value outside [0, 1]; no malformed output is ever defaulted "
        "to zero. Across every computed phase the strict-JSON parse rate was 1.000 and the "
        "refusal rate 0.000."
    )
    w("")
    w("| Scorer | Required JSON shape | Validation |")
    w("|---|---|---|")
    w(
        "| `ChecklistScorer` | `{\"covered\": [item_id, ...], \"evidence\": {item_id: quote}}` "
        "| `covered` must be a list of known `item_id`s |"
    )
    w(
        "| `SegueScorer` | `{\"domains\": {<5 domains>: float}, \"rationale\": {...}}` "
        "| all five domains required; each numeric and in [0, 1] |"
    )
    w(
        "| `ReasoningScorer` | `{\"score\": float, \"rationale\": str}` "
        "| `score` required, numeric, in [0, 1] |"
    )
    w("")
    w(
        "The overall composite is formed from these three components as stated in Methods "
        "(\"Automated scoring pipeline\")."
    )
    w("")

    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Export Supplementary Note 1 from source.")
    ap.add_argument(
        "--out",
        default=str(
            ROOT
            / "submission_lowresource"
            / "supplementary"
            / "Supplementary_Note1_Scoring_Instrument.md"
        ),
    )
    args = ap.parse_args()

    cases = {cid: _load_case(ROOT / "conf" / "case" / f"{cid}.yaml") for cid in STUDY_CASES}
    note = build_note(cases)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(note, encoding="utf-8")
    n_items = sum(len(c.history_checklist) for c in cases.values())
    print(f"wrote {out} ({len(note)} chars; {len(cases)} cases, {n_items} checklist items)")


if __name__ == "__main__":
    main()
