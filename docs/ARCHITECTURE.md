# Architecture

`core.py` separates discovery, decoding/orientation, resizing/trimming, encoding,
and packing. `Options` is an immutable validated dataclass. Batch processing is
sequential to bound working memory; the atlas holds its processed sprites until
packing completes. Output is staged and renamed only after the operation
finishes. The GUI communicates with its worker through a queue and does not
touch Tk from worker threads. The CLI and GUI call the same public functions.

Roadmap candidates: MaxRects packing, multipage atlases, optional color-profile
conversion, cancellable batches, and a manifest-based incremental build cache.
These are not part of 0.1.0.
