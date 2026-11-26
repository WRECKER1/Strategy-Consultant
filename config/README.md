# config/ — the theory layer

These files ARE the tool's theory (Layers 1 and 2 of the midterm, §4). The code only reads them.

Rules for editing:
1. Change a file only after a group decision. Then log it in `docs/decision_log.md`.
2. Run `python -m engine.config_check` after any edit. It must say PASSED.
3. The printed fingerprint changes whenever the theory changes. Never edit these files between cases in one validation round: the generalisability test requires the same fingerprint for every case.
4. Comments starting `MT §` cite the midterm section, and `D-xx` cites the decision log.

Case-specific information (context profile, sources) never goes here. It goes in `cases/<case_id>/`.
