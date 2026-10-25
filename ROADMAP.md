# AssetFlow roadmap

This is a proposal list, not a delivery promise. Reliability and reproducible bugs take
priority over feature count. Discuss a concrete use case before starting large changes.

## Current release

- Add a real before/after preview using the encoded output, including visible alpha checkerboards.
- Cancel batches without publishing partial output; keep original files unchanged.
- Avoid retaining all decoded sprites in atlas memory; skip symlink directories and bound GUI logs.

## Candidate contributions

- [ ] Atlas JSON reconstruction example for game developers.
- [ ] Optional ICC-to-sRGB conversion with pixel/color regression fixtures.
- [ ] Multipage atlas packing after demand and memory measurements.

## Feedback and evidence

For each accepted improvement record its issue, minimal reproduction, fix PR and test.
Ask early testers which task they tried, whether they completed it, their OS and the
first obstacle. Record distinct willing testers only with consent; do not identify
anonymous downloads as users. No telemetry is installed in the applications.

Track real stars/forks, external merged PRs, resolved user bugs and release asset download
counts with a dated GitHub snapshot. Raw asset downloads include possible repeats/automation
and are not unique users. Exclude maintainer validation downloads from adoption claims.
Never buy/exchange stars, create fake accounts, manufacture testimonials, or submit
trivial contributions to reach an eligibility threshold.
