# Krita model-input modes

Status: **implemented in development; automated gates pass; real-Krita host
qualification is still required**.

This additive feature does not modify the published GapFill for Krita 1.0.2
tag or artifact. Version 1.0.2 remains the qualified Line-only release. A later
feature release would normally use version 1.1.0 after host qualification.

## Contracts kept separate

The bundled model was trained with a binary Line-only channel 0 and target-gap
channel 1. The ONNX bytes, input/output names, shape `[1,2,32,32]`, and provider
policy are unchanged.

The development Docker exposes two prediction modes:

| Serialized value | Display | Channel 0 |
| --- | --- | --- |
| `line_only` | Line only | canonical Line boundary |
| `line_or_guides` | Line + Guides | canonical Line OR normalized effective Guide boundary |

`line_only` is the default for a fresh installation, an upgrade with no stored
key, and an unrecognized stored value. The setting is stored under
`modelBoundaryMode`; display text is never serialized.

Guide normalization uses the same any-nonzero-alpha binary boundary supplied
to Krita detection. In `line_or_guides`, a target Guide gap removes only its
own target-gap pixels from the Guide contribution before the OR. Channel 1 is
unchanged. Detection always uses Line OR Guides and is independent of this
selector. Full-image, Line-derived semantic regions, output scoring, Apply,
and all host mutation rules are also unchanged.

The Web product has its own restored compatibility runtime policy. Matching
normalized inputs give matching Line-or-effective-Guides composition, but this
does not redefine the Line-only training contract or the published 1.0.2
Krita default.

## Frozen-session boundary

Scan freezes the selected enum through the controller, worker, predictor, and
tensor builder. Every prediction and session checkpoint records that mode.
Changing the selector during a running or published analysis cancels/retire the
worker, removes the overlay, clears candidates and known history checkpoints,
and asks for a new explicit Scan. It does not rescan or invoke inference.
Undo/Redo reconciliation rejects a checkpoint from another mode.

## Automated evidence

The host-independent suite covers:

- missing, invalid, and persisted settings;
- exact default/explicit Line-only tensor identity;
- exact Line-or-Guides OR composition and target Guide-gap exclusion;
- unchanged target channel and detection topology;
- mode propagation through worker/predictor metadata;
- frozen checkpoint identity and fail-closed cross-mode restoration;
- mode-change invalidation without constructing a new worker;
- Apply/Undo restoration in each mode, plus the existing interaction,
  persistent-session, external-mutation, importer, release-freeze, and
  Line-only parity regressions.

These tests do not establish real-host qualification.

## Minimal real-Krita smoke plan

Use a disposable fixture whose normalized Guide geometry changes channel 0 and,
preferably, its prediction:

1. start without a stored mode and confirm **Line only**;
2. Scan, record the tensor/prediction identity, and leave the session active;
3. switch to **Line + Guides** and confirm the overlay/session disappears and a
   new Scan is required without automatic inference;
4. Scan again and verify the expected Guide contribution and prediction;
5. Apply one candidate, Undo once, and verify the same frozen second-mode
   prediction and candidate return without inference;
6. switch back to **Line only** and confirm another explicit Scan is required;
7. restart Krita after selecting **Line + Guides** and confirm persistence.

The smoke must also confirm that correction, magnifier, sweep, native Apply,
and known-checkpoint Undo/Redo behavior remain intact. Do not publish or claim
support for the new mode until this real-host smoke succeeds on the intended
support cell.
