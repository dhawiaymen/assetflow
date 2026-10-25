# Asset and atlas formats

Optimization writes `manifest.json` with options, successful files, errors,
duplicates, input/output byte totals, and saved bytes. SHA-256 refers to each
encoded output. The duplicate key compares processed dimensions and RGBA pixels,
not source encoding. Lossy formats can differ from those processed pixels.

Atlas frame coordinates exclude padding and extrusion. For a frame with
`frame={x:8,y:8,w:40,h:50}` and `spriteSourceSize={x:10,y:20,w:40,h:50}`,
copy the 40×50 atlas region to (10,20) on a transparent sourceSize canvas.
Coordinates are integer pixels with a top-left origin.

Padding is fully transparent space outside the extruded edge. Extrusion copies
the outermost pixel rows, columns, and corners to reduce texture filtering bleed.
It does not change frame coordinates or source dimensions. Atlas packing uses
height-descending shelves with deterministic filename tie-breaking. Sprites are
never rotated, scaled to fit an atlas, or cropped to hide an overflow.

The JSON uses common TexturePacker-style fields but no engine-specific loader
compatibility is guaranteed. Read `frame` and trim offsets explicitly in your
engine. Tests reconstruct original sprites directly from these fields.
