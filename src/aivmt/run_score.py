"""Hydra entrypoint: score one recorded encounter with a configured model.

Usage:
    uv run --extra serve python -m aivmt.run_score \\
        llm.name=openai_compat llm.base_url=http://localhost:8000/v1 \\
        transcript_path=data/encounters/enc_1.json out_path=outputs/enc_1_scored.json
Use ``llm.name=mock`` to dry-run without a model.
"""

from __future__ import annotations


def main() -> None:
    import hydra
    from omegaconf import DictConfig, OmegaConf

    @hydra.main(version_base=None, config_path="../../conf", config_name="config")
    def _run(cfg: "DictConfig") -> None:
        from .cases import case_from_dict
        from .dataio import load_encounter, save_encounter, transcript_from_dict
        from .llm import LLMFactory
        from .pipeline import ScoringPipeline
        from .utils import get_logger, set_seed

        log = get_logger("aivmt.run_score")
        set_seed(int(cfg.get("seed", 42)))

        transcript_path = cfg.get("transcript_path")
        if not transcript_path:
            log.error("set transcript_path=<path to a saved encounter json>")
            return

        case_cfg = OmegaConf.to_container(cfg.case, resolve=True)
        llm_cfg = OmegaConf.to_container(cfg.llm, resolve=True)
        assert isinstance(case_cfg, dict) and isinstance(llm_cfg, dict)
        case = case_from_dict(case_cfg)
        llm = LLMFactory(str(llm_cfg.pop("name")), **llm_cfg)

        record = load_encounter(transcript_path)
        transcript = transcript_from_dict(record.get("transcript", record))

        result = ScoringPipeline(llm).run(case, transcript)
        out = save_encounter(result, transcript, cfg.get("out_path", "outputs/encounter_scored.json"))
        log.info("overall=%.3f saved=%s", result.score.overall, out)

    _run()


if __name__ == "__main__":
    main()
