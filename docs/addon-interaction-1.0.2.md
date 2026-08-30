# GapFill for Krita 1.0.2 bounded interaction evidence

Status: **GAPFILL INTERACTION PATCH BOUNDED REAL-HOST SMOKE PASS**.

This record consolidates the post-1.0.1 interaction/lifecycle patch evidence.
It does not rerun or rewrite the historical Phase 6.5 A–V matrix, and it does
not broaden the supported host cell.

## Host and fixture

The bounded smoke used Windows x64 with Krita 5.3.3 git `858d352`, Qt 5.15.7,
embedded CPython 3.13.5 (64-bit), and PyQt5 5.15.11. The disposable fixture
contained three learned candidates:

| Candidate | Center | Frozen prediction | Confidence |
| --- | --- | --- | --- |
| `gap-0` | `(100, 150)` | `(255, 0, 0)` | `0.3384663447504863` |
| `gap-1` | `(100, 350)` | `(0, 255, 0)` | `0.3384663447504863` |
| `gap-2` | `(455, 455)` | `(255, 255, 0)` | `0.3384663447504863` |

## Bounded real-host results

- Ordinary pointer movement remained free with the overlay active. The overlay
  is mouse-transparent, observes events through a passive application filter,
  and does not grab or warp the pointer.
- Hover magnification passed for A → B switching, move-away disappearance,
  and canvas leave/re-enter recovery.
- Applying candidates preserved the frozen session: resolved candidates were
  removed, remaining candidates retained their original scan and prediction,
  the overlay stayed active, no worker or inference reran, and no invisible
  rescan occurred.
- Magnifier sampling used the represented source image. The RED source remained
  selectable when the physical canvas beneath the popup was BLUE.
- The dotted correction connector ended at the final displayed popup center.
- Sweep pointer routing passed without a stuck OS pointer or stale Krita canvas
  cursor. Empty-space sweep applied nothing; sweeping one candidate applied
  exactly that candidate and retained the remaining frozen session.
- Sweep gestures displayed the temporary pale yellow-green trail and cleared it
  at release or teardown.
- One-level known GapFill Undo restored candidate membership.
- Correct RED prediction → BLUE correction → Apply → Undo restored the
  Coloring bytes and the original RED frozen prediction; the stale BLUE preview
  did not return.
- Two known GapFill applies followed by two Undo operations restored the exact
  earlier checkpoints. Two corresponding Redo operations restored the two known
  later checkpoints. This is bounded evidence, not a claim about arbitrary
  document-history graphs.
- Immediate Undo after the final candidate exhausted the overlay restored the
  candidate and frozen session.
- No crash or plugin-load failure was reported across the final successful
  interactions. This is not a claim about operations outside this smoke.

The retained real-host Coloring identities include initial checkpoint H0
`28bbd41aa77bd7c6322921af6cb94ac2f70de87c813f39f1feef9266518f2968`,
the initial RED Apply H1
`bd258e568ba2df576f9236a080fe691e3eb7ec34f3f0a21aa729f436bada8b89`,
and the corrected BLUE Apply checkpoint
`8b76704ce1a926ae326a32bf0580829401d576a589655bf29a4781d6fcfb1bd8`.

## Deliberately skipped manual case

`MANUAL_EXTERNAL_MUTATION_FAIL_CLOSED_SMOKE_SKIPPED_BY_SCOPE`

No artificial Scripter mutation was injected during the active overlay. Current
automated regressions instead prove that an unknown Coloring/composite hash or
non-adjacent history state cannot reuse stale analysis or apply a stale
candidate: the session is invalidated, its gate is retired, and no rescan is
started. Related regressions cover document/view replacement, stale target or
native state, history-branch divergence, overlapping invalidated candidates,
shutdown disconnection, and overlay teardown.

## Boundary

This bounded smoke does not claim full Phase 6.5 A–V requalification, arbitrary
Krita host support, HiDPI qualification, arbitrary split-view support, or full
application-close qualification with an active worker. Historical Phase 6.5
limits remain authoritative.
