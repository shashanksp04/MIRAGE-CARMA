# Conference scenario validation

Status: **pending cluster compute**. No real inference recording or validated
conference input bundle is available in this checkout. `catalog.json` contains
editable, explicitly unvalidated starter questions.

For each real scenario record:

| Field | Required record |
| --- | --- |
| Capability | Management direct retrieval, management augmentation, or image identification |
| Input | Exact question, context, task type and owned image/source provenance |
| Run | Saved run ID and timestamp; complete or truncated trace |
| Configuration | Effective feature snapshot, model IDs and endpoint allocation |
| Runtime | Collection identity, points before/after and accumulation conditions |
| Observed behavior | Actual events, evidence, extraction/search/ingestion outcomes |
| Validation | Reviewer/date and repeatability notes; no guaranteed invented path |

Keep private inputs and keys out of public scenario assets. Set a catalog entry's
`validated` field only after recording supporting real results. Preserve the
corresponding run store and owned images for replay; history retention can prune
recordings. See `../CONFERENCE-RUNBOOK.md` for conference operation and fallback.
