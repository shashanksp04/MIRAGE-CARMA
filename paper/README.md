# MIRAGE-CARMA Paper Workspace

This directory contains manuscript sections, internal evidence notes, and section reviews. Manuscript files are written as publication prose; implementation evidence and unresolved details are maintained under `notes/`.

## Scope

The active manuscript covers the Introduction, Related Work, Methodology, Experimental Setup, and Limitations. Results, empirical Discussion, and Conclusion remain outside this workspace until experimental outcomes are available.

## Evidence and review policy

Implementation claims must be traceable to the repository or explicitly marked `[DETAIL REQUIRES VERIFICATION]`. Literature claims must have an entry in `notes/citation_notes.md`. Each manuscript section receives an independent critique in `reviews/`, followed by a revision by the section's writer and a final cross-section consistency pass.

## Current manuscript state

- `01_introduction.md`: drafted, independently reviewed, revised, and integrated.
- `02_related_work.md`: drafted from primary sources, independently reviewed, revised, and integrated.
- `03_methodology.md`: drafted from implementation evidence, independently reviewed, revised, and integrated.
- `04_experimental_setup.md`: drafted jointly for model/ablation and protocol coverage, independently reviewed, revised, and integrated.
- `05_limitations.md`: drafted, independently reviewed, revised, and integrated.

The remaining verification markers concern experimental artifacts or author decisions that are absent from the repository, chiefly the final system name, Qwen-3 role and serving configuration, authoritative nine-condition matrix, realized corpus and crop-dictionary artifacts, run manifests, runtime-memory policy, final cohort, and judge protocol.
