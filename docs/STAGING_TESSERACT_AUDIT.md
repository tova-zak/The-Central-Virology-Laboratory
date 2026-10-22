# Staging Tesseract audit — 2026-10-22

Target: `virology-lab-staging-backend`.

## Verified in source

- GitHub main at inspection: `f6ca6bfd7c4fa0557bb3db7d639945eb317b50fc`, merging release PR #13.
- `backend/Dockerfile` installs `tesseract-ocr`, `tesseract-ocr-heb`, and `tesseract-ocr-eng`. `backend/requirements.txt` includes `pytesseract`.
- `render.yaml` selects Docker, backend root, `./Dockerfile`, context `.`, branch main, manual deployments, `/ready` health check.
- Blueprint values: `HYBRID_ENGINE_ENABLED=false`, `HYBRID_ENABLE_OCR=false`, `HYBRID_ENABLE_HYBRID_VERIFICATION=false`, focused retry false. Application defaults alone are insufficient to establish the active cloud flags.
- OCR execution uses both `settings.enable_ocr` and hybrid configuration `enable_ocr`. The probe reports that effective conjunction and the separate engine master switch; OCR may run independently of the engine master switch when its own flags permit it.

## Not verified on Render

No authenticated Render session or Render API credentials were available in this task. Dashboard navigation timed out; tab inventory subsequently showed `/login`. The running service's runtime, deployed commit, overrides, binary version, and language files therefore remain **unverified**. Source configuration does not prove that the running container uses it. No cloud deploy or restart was performed.

## Prepared change

`app/core/ocr_diagnostics.py` runs once per application process during lifespan startup in a worker thread, before deployment/storage validation. It checks PATH, probes the configured executable (or PATH executable), logs a parsed numeric version, safe language identifiers, missing `heb`/`eng`, effective OCR/verification flags, and the engine master flag. Version and language probes each time out after two seconds. Failures cannot stop application startup. No OCR documents, provider calls, database operations, environment dumps, paths, raw stderr, or exception messages are logged by this diagnostic. Existing startup validation/storage readiness is unchanged.

Four isolated mocked tests pass. These tests prove probe behavior, **not cloud installation**. Docker image build and cloud execution were not performed.

## Approval-ready deployment and acceptance

1. Review this branch and merge only the diagnostic, its tests, and this report into main after approval. No Dockerfile or feature-flag changes are needed in the source inspected.
2. In the authenticated Render dashboard, confirm the target service uses Docker with the paths above. Record its current deployed commit and compare it with the approved commit; check only the named boolean flags. Keep the engine and existing disabled features disabled. Do not export all environment values.
3. Manually deploy the approved commit only after deployment approval. Startup performs the metadata probes automatically; do not upload documents, invoke processing, or run migrations for this audit.
4. Inspect only `OCR startup:` log entries. Require `binary_in_path=True`, a numeric version with `version_probe=ok`, `language_probe=ok`, `languages` including `eng,heb`, `missing_required_languages=none`, and `runtime_ready=True`. Confirm the separate `ocr_enabled` and `hybrid_engine_enabled` values; this deployment must not enable the hybrid engine.

## Minimal correction if cloud probes fail

- Binary missing: confirm Docker runtime and the expected deployed Dockerfile/commit. The inspected image already installs it; redeploying that image is the minimal correction if the active service uses another build. If a different Dockerfile is active, add `tesseract-ocr` to its apt installation.
- Missing Hebrew or English: add only `tesseract-ocr-heb` or `tesseract-ocr-eng` to the active Dockerfile, respectively, and rebuild after approval. Both are already present in this source.
- Binary exists but probes fail: check whether `HYBRID_TESSERACT_CMD` or `TESSERACT_CMD` overrides the image binary, and whether `TESSDATA_PREFIX` redirects language lookup. Correct the relevant setting after review; do not print its raw value in application logs.
- `runtime_ready=True` with `ocr_enabled=False`: installation supports cloud OCR, but the application flag currently disables it. Enabling OCR is a separate approved change; this audit changes no flags.

**Conclusion:** this Docker build is configured to support Hebrew/English OCR in the cloud. Actual installation and current cloud OCR availability cannot yet be certified. No missing package has been demonstrated in the running service; the missing evidence is authenticated runtime/configuration access and startup logs from an approved deployment.
