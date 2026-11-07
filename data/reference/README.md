# Reference data

Official figures Haven's engines calculate with (council tax, energy rates, EPC-derived energy
use, rent context). One YAML file per dataset, loaded by `haven.reference`.

Every `*.yaml` file here **must** start with a provenance block:

```yaml
meta:
  source_url: https://...   # the official page or file the figures came from
  retrieved: 2026-11-07     # date the source was read (never in the future)
  licence: OGL v3.0         # the source's licence
  notes: How the figures were extracted, caveats, known gaps.
```

`backend/tests/reference/test_provenance.py` fails if any file lacks these fields or has a
future `retrieved` date. Never invent or transcribe figures from third-party sites; files are
produced by the ingest scripts in `backend/scripts/` where possible.
