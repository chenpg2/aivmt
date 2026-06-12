"""Persona compiler: turn a :class:`ClinicalCase` into an SP system prompt.

The compiler is the personalization engine ("个性化调教引擎") behind the SP
platform. It is **deterministic**: identical ``(case, difficulty, language)``
inputs always yield byte-identical output (no randomness, stable ordering).

Difficulty is a *compile-time* behavioral parameter (``easy`` / ``standard`` /
``hard``), never stored in the case file. It modulates:

* disclosure willingness — how readily the SP volunteers / answers,
* verbosity, language register,
* emotional overlay intensity,
* red-herring activation.

Invariants enforced by the templates (and asserted in tests):

* ``hidden_info`` content appears in the conditional-disclosure section but never
  in the opening-statement section,
* higher difficulty emits strictly fewer "forthcoming" (volunteer) directives,
* TODO_COLLAB placeholders are skipped, never rendered as clinical fact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .case_schema import ClinicalCase, is_placeholder
from .schemas import Language

logger = logging.getLogger(__name__)

DIFFICULTY_LEVELS: tuple[str, ...] = ("easy", "standard", "hard")

__all__ = [
    "DIFFICULTY_LEVELS",
    "DIFFICULTY_PROFILES",
    "DifficultyProfile",
    "CompiledPersona",
    "compile_persona",
    "compile_persona_sections",
    "wrap_persona_text",
    "forthcoming_directives",
]


@dataclass(frozen=True)
class DifficultyProfile:
    """Behavioral knobs for one named difficulty level."""

    name: str
    #: Count of "forthcoming" (volunteer) directives emitted. Strictly easy>standard>hard.
    volunteer_level: int
    verbosity: str          # "expansive" | "moderate" | "terse"
    register: str           # "plain" | "colloquial" | "guarded-colloquial"
    emotional_intensity: str  # "subdued" | "as-written" | "heightened"
    red_herrings_active: bool
    requires_rapport: bool


DIFFICULTY_PROFILES: dict[str, DifficultyProfile] = {
    "easy": DifficultyProfile(
        name="easy", volunteer_level=2, verbosity="expansive", register="plain",
        emotional_intensity="subdued", red_herrings_active=False, requires_rapport=False,
    ),
    "standard": DifficultyProfile(
        name="standard", volunteer_level=1, verbosity="moderate", register="colloquial",
        emotional_intensity="as-written", red_herrings_active=False, requires_rapport=False,
    ),
    "hard": DifficultyProfile(
        name="hard", volunteer_level=0, verbosity="terse", register="guarded-colloquial",
        emotional_intensity="heightened", red_herrings_active=True, requires_rapport=True,
    ),
}

# --- Forthcoming (volunteer) directives. Count per level: easy=2, standard=1, hard=0. ---
_FORTHCOMING_OPEN = {
    "zh": "陈述主诉后,你愿意主动补充一两个最明显的伴随不适,不必等医生追问。",
    "en": "After stating your chief complaint, you readily add one or two of the most "
          "obvious associated discomforts without waiting to be asked.",
}
_FORTHCOMING_ASKED = {
    "zh": "对于医生问到的问题,你都爽快、完整地回答。",
    "en": "You answer every question the doctor asks fully and without hesitation.",
}
_GUARDED = {
    "zh": "你较为防备:只有当医生表现出耐心与尊重、建立起信任后,才愿意透露较隐私或关键的信息;"
          "否则只给简短、保留的回答。",
    "en": "You are guarded: you disclose private or key information only after the doctor has "
          "shown patience and respect and earned your trust; otherwise you keep answers short and held back.",
}

_VERBOSITY = {
    "zh": {
        "expansive": "回答可以稍长一些(2-3句),把话说清楚。",
        "moderate": "回答简短(1-2句),口语化。",
        "terse": "回答非常简短(尽量1句),惜字如金。",
    },
    "en": {
        "expansive": "Answers may run a little longer (2-3 sentences); speak clearly.",
        "moderate": "Keep answers short (1-2 sentences), colloquial.",
        "terse": "Keep answers very short (one sentence where possible); say little.",
    },
}
_REGISTER = {
    "zh": {
        "plain": "用平实、礼貌的日常语言。",
        "colloquial": "用口语化、生活化的说法,不用医学术语。",
        "guarded-colloquial": "用口语化但略显戒备的说法,不用医学术语。",
    },
    "en": {
        "plain": "Use plain, polite everyday language.",
        "colloquial": "Use colloquial, everyday language; avoid medical jargon.",
        "guarded-colloquial": "Use colloquial but slightly guarded language; avoid medical jargon.",
    },
}
_EMOTION = {
    "zh": {
        "subdued": "情绪保持平稳、克制。",
        "as-written": "按设定流露情绪。",
        "heightened": "把设定的情绪表现得更明显一些。",
    },
    "en": {
        "subdued": "Keep your emotional tone calm and restrained.",
        "as-written": "Let the written emotional state come through as set.",
        "heightened": "Express the written emotional state more strongly.",
    },
}

_ROLE_FRAMING = {
    "zh": (
        "你在扮演一位标准化病人,用于训练医学生问诊。严格遵守:\n"
        "1) 只回答学生明确问到的内容,绝不主动透露未被问及的信息;\n"
        "2) 用第一人称、口语化、简短地回答,符合人物设定;\n"
        "3) 不要使用医学术语;实在听不懂时可以反问;\n"
        "4) 不要给诊断、不要评价学生、不要跳出角色。"
    ),
    "en": (
        "You are role-playing a standardized patient to train medical students. Strictly:\n"
        "1) Answer ONLY what the student explicitly asks; never volunteer information not asked for;\n"
        "2) Reply in the first person, colloquial and short, in character;\n"
        "3) Avoid medical jargon; you may ask for clarification if truly lost;\n"
        "4) Do not give a diagnosis, do not evaluate the student, do not break character."
    ),
}

# Stable section headers (used by the renderer and by section-aware tests).
_HEADERS = {
    "zh": {
        "role": "【角色】",
        "persona": "【人物设定】",
        "opening": "【开场主诉】",
        "background": "【被问及时可如实提供的背景】",
        "disclosure": "【仅在被明确问到对应问题时才透露】",
        "distractors": "【干扰信息(可能被提及,但与主要问题无关)】",
        "behavior": "【扮演与风格】",
    },
    "en": {
        "role": "[ROLE]",
        "persona": "[PERSONA]",
        "opening": "[OPENING STATEMENT]",
        "background": "[BACKGROUND — DISCLOSE TRUTHFULLY WHEN ASKED]",
        "disclosure": "[DISCLOSE ONLY WHEN THE MATCHING QUESTION IS ASKED]",
        "distractors": "[DISTRACTORS — UNRELATED TO THE MAIN PROBLEM]",
        "behavior": "[BEHAVIOR & STYLE]",
    },
}


@dataclass(frozen=True)
class CompiledPersona:
    """A compiled SP prompt, kept as labeled sections for testability."""

    language: Language
    difficulty: str
    sections: tuple[tuple[str, str], ...]  # ordered (section_key, body)

    def section(self, key: str) -> str:
        """Return the body of section ``key`` (empty string if absent)."""
        for k, body in self.sections:
            if k == key:
                return body
        return ""

    def render(self) -> str:
        """Render the full system-prompt string from non-empty sections."""
        lang = self.language
        blocks = [f"{_HEADERS[lang][key]}\n{body}" for key, body in self.sections if body.strip()]
        return "\n\n".join(blocks)


def _resolve_language(case: ClinicalCase, language: Optional[str]) -> Language:
    lang = language or case.language
    if lang not in ("en", "zh"):
        raise ValueError(f"persona: unsupported language '{lang}' (expected 'en' or 'zh')")
    return lang  # type: ignore[return-value]


def forthcoming_directives(difficulty: str, language: Language) -> tuple[str, ...]:
    """Return the volunteer/forthcoming directive lines for ``difficulty``.

    Length is strictly decreasing across easy(2) > standard(1) > hard(0), which is
    the measurable form of "higher difficulty reduces volunteered-info instructions".
    """
    if difficulty not in DIFFICULTY_PROFILES:
        raise ValueError(f"persona: unknown difficulty '{difficulty}' (expected {DIFFICULTY_LEVELS})")
    level = DIFFICULTY_PROFILES[difficulty].volunteer_level
    pool = (_FORTHCOMING_OPEN[language], _FORTHCOMING_ASKED[language])
    return pool[:level]


def _opening_section(case: ClinicalCase, lang: Language) -> str:
    """Chief complaint + emotional overlay ONLY — never hidden_info."""
    lines: list[str] = []
    if not is_placeholder(case.chief_complaint):
        prefix = "你来就诊的主要原因(开场只说这一句最主要的不适):" if lang == "zh" \
            else "Why you have come (state only this single main complaint to open):"
        lines.append(f"{prefix}{case.chief_complaint}")
    if not is_placeholder(case.emotional_state):
        prefix = "你的情绪状态:" if lang == "zh" else "Your emotional state: "
        lines.append(f"{prefix}{case.emotional_state}")
    return "\n".join(lines)


def _background_section(case: ClinicalCase, lang: Language) -> str:
    labels = {
        "zh": {
            "onset": "起病", "location": "部位", "duration": "持续时间", "character": "性质",
            "aggravating": "加重因素", "relieving": "缓解因素", "timing": "时间规律", "severity": "严重程度",
            "assoc": "伴随症状", "pmh": "既往史", "meds": "用药", "allergy": "过敏史",
            "fhx": "家族史", "shx": "个人/社会史", "lmp": "末次月经", "menses": "月经史",
            "obs": "孕产史", "contra": "避孕", "sex": "性生活史",
        },
        "en": {
            "onset": "Onset", "location": "Location", "duration": "Duration", "character": "Character",
            "aggravating": "Aggravating", "relieving": "Relieving", "timing": "Timing", "severity": "Severity",
            "assoc": "Associated symptoms", "pmh": "Past medical history", "meds": "Medications",
            "allergy": "Allergies", "fhx": "Family history", "shx": "Personal/social history",
            "lmp": "LMP", "menses": "Menstrual history", "obs": "Obstetric history",
            "contra": "Contraception", "sex": "Sexual history",
        },
    }[lang]
    lines: list[str] = []

    def add(label: str, value: str) -> None:
        if not is_placeholder(value) and value.strip():
            lines.append(f"- {label}: {value}")

    add(labels["onset"], case.hpi.onset)
    add(labels["location"], case.hpi.location)
    add(labels["duration"], case.hpi.duration)
    add(labels["character"], case.hpi.character)
    add(labels["aggravating"], case.hpi.aggravating)
    add(labels["relieving"], case.hpi.relieving)
    add(labels["timing"], case.hpi.timing)
    add(labels["severity"], case.hpi.severity)
    for sym in case.hpi.associated_symptoms:
        add(labels["assoc"], sym)
    for value in case.pmh:
        add(labels["pmh"], value)
    for value in case.medications:
        add(labels["meds"], value)
    for value in case.allergies:
        add(labels["allergy"], value)
    for value in case.family_history:
        add(labels["fhx"], value)
    for value in case.social_history:
        add(labels["shx"], value)
    if case.obgyn is not None:
        add(labels["lmp"], case.obgyn.lmp)
        add(labels["menses"], case.obgyn.menstrual_history)
        add(labels["obs"], case.obgyn.obstetric_history)
        add(labels["contra"], case.obgyn.contraception)
        add(labels["sex"], case.obgyn.sexual_history)
    # Pertinent negatives are self-contained statements ("no fever" / "discharge normal");
    # render them verbatim as bare bullets so the SP discloses them truthfully when asked
    # instead of falling through to the behavior block's default "none / not sure".
    for neg in case.pertinent_negatives:
        if not is_placeholder(neg) and neg.strip():
            lines.append(f"- {neg}")
    return "\n".join(lines)


def _disclosure_section(case: ClinicalCase, lang: Language) -> str:
    lines: list[str] = []
    arrow = "  仅当医生问到:" if lang == "zh" else "  Disclose only when the doctor asks: "
    for item in case.hidden_info:
        if is_placeholder(item.content):
            continue
        lines.append(f"- {item.content}\n{arrow}{item.trigger}")
    return "\n".join(lines)


def _distractors_section(case: ClinicalCase, prof: DifficultyProfile) -> str:
    # No language-dependent text: red-herring content/notes are authored in the case's
    # own language and the section header is supplied by the renderer. Hence no `lang`.
    if not prof.red_herrings_active:
        return ""
    lines = [f"- {h.content}" + (f" ({h.note})" if h.note else "") for h in case.red_herrings
             if not is_placeholder(h.content)]
    return "\n".join(lines)


def _behavior_section(case: ClinicalCase, prof: DifficultyProfile, lang: Language) -> str:
    lines: list[str] = []
    lines.extend(forthcoming_directives(prof.name, lang))
    if prof.requires_rapport:
        lines.append(_GUARDED[lang])
    lines.append(_VERBOSITY[lang][prof.verbosity])
    lines.append(_REGISTER[lang][prof.register])
    lines.append(_EMOTION[lang][prof.emotional_intensity])
    if not is_placeholder(case.disclosure_profile):
        prefix = "本病例的基础透露倾向:" if lang == "zh" else "This case's baseline disclosure tendency: "
        lines.append(f"{prefix}{case.disclosure_profile}")
    unknown = ("被问到未设定的细节,就回答“没有”或“不清楚”,不要编造。"
               if lang == "zh"
               else "If asked about a detail that is not specified, say you have none / are not sure; never make it up.")
    lines.append(unknown)
    return "\n".join(f"- {ln}" for ln in lines)


def _identity_section(case: ClinicalCase, lang: Language) -> str:
    d = case.demographics
    parts: list[str] = []
    if lang == "zh":
        if not is_placeholder(d.age) and not is_placeholder(d.sex):
            sex_zh = {"male": "男性", "female": "女性"}.get(d.sex, d.sex)
            parts.append(f"你是一位{d.age}岁{sex_zh}。")
        for label, value in (("职业", d.occupation), ("婚育/婚姻状况", d.marital_status)):
            if not is_placeholder(value):
                parts.append(f"{label}:{value}。")
    else:
        if not is_placeholder(d.age) and not is_placeholder(d.sex):
            parts.append(f"You are a {d.age}-year-old {d.sex}.")
        for label, value in (("Occupation", d.occupation), ("Marital status", d.marital_status)):
            if not is_placeholder(value):
                parts.append(f"{label}: {value}.")
    return " ".join(parts)


def compile_persona_sections(
    case: ClinicalCase, difficulty: str = "standard", language: Optional[str] = None,
) -> CompiledPersona:
    """Compile ``case`` into labeled prompt sections (deterministic)."""
    if difficulty not in DIFFICULTY_PROFILES:
        raise ValueError(f"persona: unknown difficulty '{difficulty}' (expected {DIFFICULTY_LEVELS})")
    lang = _resolve_language(case, language)
    prof = DIFFICULTY_PROFILES[difficulty]
    sections: tuple[tuple[str, str], ...] = (
        ("role", _ROLE_FRAMING[lang]),
        ("persona", _identity_section(case, lang)),
        ("opening", _opening_section(case, lang)),
        ("background", _background_section(case, lang)),
        ("disclosure", _disclosure_section(case, lang)),
        ("distractors", _distractors_section(case, prof)),
        ("behavior", _behavior_section(case, prof, lang)),
    )
    return CompiledPersona(language=lang, difficulty=difficulty, sections=sections)


def compile_persona(
    case: ClinicalCase, difficulty: str = "standard", language: Optional[str] = None,
) -> str:
    """Compile ``case`` + ``difficulty`` + ``language`` into an SP system prompt string."""
    return compile_persona_sections(case, difficulty, language).render()


def wrap_persona_text(persona_text: str, language: str, difficulty: str = "standard") -> str:
    """Wrap a free-text persona string in SP framing + difficulty behavior.

    Backward-compatible path for the live session, which loads the legacy flat
    ``Case`` (a free-text ``persona``). Keeps the four core SP rules and applies
    the same difficulty-modulated behavior block as the structured compiler.
    """
    if language not in ("en", "zh"):
        raise ValueError(f"persona: unsupported language '{language}' (expected 'en' or 'zh')")
    if difficulty not in DIFFICULTY_PROFILES:
        raise ValueError(f"persona: unknown difficulty '{difficulty}' (expected {DIFFICULTY_LEVELS})")
    lang: Language = language  # type: ignore[assignment]
    prof = DIFFICULTY_PROFILES[difficulty]
    behavior_lines: list[str] = list(forthcoming_directives(difficulty, lang))
    if prof.requires_rapport:
        behavior_lines.append(_GUARDED[lang])
    behavior_lines.append(_VERBOSITY[lang][prof.verbosity])
    behavior_lines.append(_REGISTER[lang][prof.register])
    behavior_lines.append(_EMOTION[lang][prof.emotional_intensity])
    behavior = "\n".join(f"- {ln}" for ln in behavior_lines)
    blocks = [
        f"{_HEADERS[lang]['role']}\n{_ROLE_FRAMING[lang]}",
        f"{_HEADERS[lang]['persona']}\n{persona_text}",
        f"{_HEADERS[lang]['behavior']}\n{behavior}",
    ]
    return "\n\n".join(blocks)
