# Phase 6 real-Krita qualification kit

This directory is a versioned test kit, not evidence that a Krita host passed.
At the Phase 6 handoff no Krita executable or embedded `krita` Python module was
available in the audit environment. Every row in `matrix.json` is therefore
`UNTESTED`.

## Generate the documents

Run `generate_fixtures.py` from Krita's Scripter plug-in after editing the final
two path arguments. It creates deterministic `.kra` documents in the requested
output directory. The two real-art documents are assembled from the frozen
Phase 2 corpus; the remaining documents are generated from byte-exact layer
recipes. Keep the generated SHA-256 values with the host test record.

The generator covers ordinary and Guide enclosures, the known real-art cases,
multiple colors, a moved target, a target with masks, a soft selection, and
asymmetric corner landmarks. `alternate-profile.kra` is generated only when the
host offers a second RGBA/U8 profile; record the selected profile name.

## Execute the matrix

Copy `matrix.json` for each exact Krita build and fill only observed results.
Record Krita, Qt/PyQt, embedded Python, OS/architecture, resource directory,
plug-in ZIP SHA-256, model SHA-256, and every generated document SHA-256.

Pixel/state checks take precedence over screenshots. In particular:

- compare the adapter snapshot arrays with the recipe/source PNG bytes;
- compare candidates and predictions with a direct pure-engine run;
- inspect raw Coloring bytes before/after apply and after Undo/redo;
- distinguish a null global selection from an allocated empty selection;
- record foreground, active node, tool state, and visible Undo steps;
- test stale edits before pressing Apply;
- exercise Stop/deactivate/shutdown at the documented cancellation boundaries;
- verify pan/zoom at DPR 1; rotation, mirror, HiDPI, ambiguous split-view widget
  discovery, moved/effected Coloring targets must fail closed in this build.

Frozen host-parity observations:

- `E101_ex2_ordinary_crop`: indices `[496, 528, 560]`, RGB `(251, 98, 115)`,
  learned score `0.913528784`;
- `E102_ex2_guide_crop`: index `[729]`, pure prediction RGB
  `(243, 242, 239)`, learned score `0.829399342`;
- the completed-art ground truth for the E102 target is yellow. That accuracy
  observation is deliberately not the Phase 6 host expectation. Host parity is
  the frozen near-white pure prediction.

Do not change `UNTESTED` to `PASS` from an offscreen Qt/fake-adapter run.
