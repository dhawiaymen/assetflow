# Changelog

## 0.1.0 — Initial public release

### Available

See the README for supported functionality and deliberate limits. This version is an
early tool release, with no production certification or community adoption claim.

### Stabilization before release

- Release Tk variables on the UI thread when a workbench is destroyed, avoiding delayed finalization in an image worker.

- Add a real before/after preview using the encoded output, including visible alpha checkerboards.
- Cancel batches without publishing partial output; keep original files unchanged.
- Avoid retaining all decoded sprites in atlas memory; skip symlink directories and bound GUI logs.

- Add regression coverage, authentic screenshots and reproducible synthetic workloads.
- Add contribution, conduct, troubleshooting and roadmap documents.
- Verify extracted Windows executables before attaching release assets; include checksums
  and dependency notices. Record actual CI evidence with each build.
