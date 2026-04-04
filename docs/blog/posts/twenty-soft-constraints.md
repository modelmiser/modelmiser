---
date: 2026-04-06
categories:
  - crossdomain
---

# Twenty Soft Constraints

When a formal model collapses composition and improvisation into one parameter.

<!-- more -->

[Part 1](../../04/compose-from-the-bass/) argued that composing FROM the
binding constraint produces designs largely unreachable by iterative
refinement. [Part 2](../../05/the-constraint-you-already-had/) argued that
sometimes the correctness machinery and the scheduling machinery turn out to
be the same system. Take constraint satisfaction literally — map a specific
creative process to it — and the formalization shows what the metaphor
couldn't.

## The model

Make Harris's constraint set explicit: arena acoustics (the low end must carry
in a 20,000-seat arena), key and tempo continuity between songs, narrative arc
within songs and across albums, singalong hooks placed for crowd
participation, the gallop as momentum engine, the current six-musician palette,
prog-rock vocabulary (odd meters, multi-section forms, instrumental breaks),
and literary source fidelity for the epics — among others. Roughly twenty in
total, running simultaneously, accumulated over five decades.

Constraint-based composition is not a metaphor. It's a real field. Torsten
Anders's Strasheela system (2007) encoded music-theory rules — counterpoint,
harmony, form — as literal constraints in the Oz programming language. Kemal
Ebcioglu's CHORAL (1988) did the same for Bach chorale harmonization. David
Cope's EMI recombined patterns under stylistic rules. The formalization
exists. What's less explored is what happens when you apply it to a living
composer with five decades of accumulated weights — and ask what the formal
structure reveals.

Three things become visible.

## Composition is improvisation with backtracking

Model a composition as a constraint satisfaction problem. The solver explores
possible note sequences, rhythmic patterns, harmonic progressions. It
proposes assignments, checks constraints, backtracks on violations, and emits
a satisfying assignment — a song.

Now vary one parameter: how far does the solver look before committing?

With unbounded lookahead and full backtracking, the solver can retract any
decision and try alternatives. This is composition. Harris tries phrases for
months, discards them, and restructures sections until every constraint is
adequately met.

With zero lookahead and no backtracking, the solver commits immediately and
never undoes. This is improvisation. A jazz musician plays a note, hears the
result, plays the next. There is no undo. The performance IS the search, and
the search terminates in real time.

These aren't categories. They're endpoints of a continuous spectrum
parameterized by search depth. Harris composes with deep search offline. A
jazz ensemble improvises with greedy search online, using audience response
and bandmate reactions as real-time constraint injection. A jam session falls
between — some backtracking (restart the verse, change the chord), but
convergence happens in minutes, not months.

The CSP formalization collapses a categorical distinction into a continuous
spectrum, which is the structural test of whether a formalization captured
something real. Practitioners on both sides think they're doing fundamentally
different things. The model says they're adjusting a single parameter.

## Every album shrinks the space

Here's where the formalization earns its keep.

If each composition is an independent CSP instance, the constraint set is
static — twenty constraints, applied fresh each time. The solution space is
wide and the same problem repeats every album.

But compositions aren't independent. Each one adds implicit constraints to
the next: don't repeat yourself. Exceed expectations. Evolve within genre
bounds. Maintain identity while demonstrating growth. These are real
constraints — Harris can't write Powerslave again even if it would satisfy
every other constraint, because anti-repetition now forbids it.

Without deliberate intervention, the implicit constraint set grows
monotonically. Each album adds. None removes. The solution space shrinks with
every release.

This has a formal consequence: eventually, the constraint system becomes
unsatisfiable. Every possible composition violates some accumulated
constraint. Creative stagnation isn't a failure of imagination. It's a
predictable consequence of monotonically growing constraint sets.

The escape hatches are real and observable. The most common is constraint
relaxation — dropping a constraint outright. Bowie killed Ziggy Stardust.
Radiohead sidelined guitars. When artists reinvent themselves, they're
relaxing constraints to reopen the solution space. The formalization tells you
which to relax: the ones whose removal maximally expands feasible territory.

A subtler move is constraint reweighting — demoting a hard constraint to soft.
Dickinson's departure from Maiden replaced a proven vocal-range constraint
with an unproven one — Bayley's different voice meant the band had to work
within a range they'd never written for. The X Factor doesn't sound like
previous Maiden because the constraint topology was surgically altered.

The third escape is domain expansion. Harris moving from shorter, rawer metal
to thirteen-minute progressive epics didn't relax existing
constraints — it opened territory where anti-repetition constraints hadn't
accumulated. You can't repeat yourself in a space you've never visited.

The sophomore album problem is the first moment the anti-repetition constraint
binds. Most bands solve it unconsciously. The formalization makes the wall
visible and suggests where the doors are.

## Walls and gradients

Not all twenty constraints work the same way. Six musicians on stage is a
wall — physics, not preference. Arena acoustics are partly wall (speed of
sound) and partly gradient (mix, arrangement density, frequency content). Key
continuity is almost entirely gradient — breakable for effect when the
narrative demands it.

Hard constraints define the shape of the feasible region — its walls. Soft
constraints define the fitness landscape within — hills and valleys.
Optimizing against a wall is wasted creative effort. Optimizing along a
gradient is where the music lives.

This is what composing FROM the constraint looks like when the constraint set
is plural: know which constraints are walls and compose along the gradients
they leave open. The formalization sharpens "work within your means" into
something actionable — it's not about humility, it's about correctly
identifying where the degrees of freedom actually are.

## The genre frontier

If Harris optimized a single objective — "best possible Iron Maiden
song" — every album would converge to a fixed style. They don't. Albums vary
because the objective function isn't one-dimensional.

Artistic satisfaction. Commercial viability. Peer respect. Technical
challenge. Legacy. These aren't reducible to a single score. A
thirteen-minute retelling of Coleridge maximizes literary ambition and
minimizes radio play. A three-minute rocker with a fist-pumping
chorus does the reverse.

Multi-objective optimization produces Pareto frontiers — the set of solutions
where improving one objective requires sacrificing another. The frontier's
shape IS the artist's territory. Maiden occupies a specific region: high
complexity, high accessibility, high commercial, high legacy. AC/DC
occupies another: moderate complexity, maximal accessibility, high commercial.
Radiohead a third: maximal complexity, low accessibility, high peer respect.

The interesting observation: these are sweet spots — regions where pushing
further along one axis actually helps adjacent axes. Maiden's prog
vocabulary makes songs more memorable, not less, because complexity creates
distinctive hooks. The sweet spot in the Pareto landscape is the formal
version of "finding your sound."

## What the model can't see

Three limitations, because a formalization that doesn't name its blind spots
isn't trustworthy.

The deepest is somatic knowledge. Harris's fingers know what comes next before
his conscious mind does — motor memory generating candidates, not evaluating
them. The CSP model treats generation as search. The biological solver treats
it as recall and mutation. The generation mechanism isn't a constraint, and
the model can't represent it.

The aesthetic gradient escapes the model entirely. In a basic
CSP, all satisfying assignments are equal. In practice, some solutions have a
quality others lack — the difference between a correct chord progression and a
haunting one. This gradient drives the solver. The model has no place for it.

Then there's serendipity — a misplayed note that sounds better than the
intended one, an accidental key change that becomes the emotional climax.
These are productive perturbations, mutation in the evolutionary sense. CSP
doesn't account for accidents, because search doesn't have them.

These aren't minor omissions. They're the things that make Harris Harris
rather than a very good constraint solver. The formalization is useful not
because it captures everything, but because the gap between what it captures
and what it misses tells you exactly where the human contribution lives.

## What the geometry shows

The constraint space, viewed as a geometric object, is where the action is:
walls and gradients, a Pareto frontier, a solution space that shrinks with
every album, and a search-depth parameter that connects composition to
improvisation.

The test of a formalization isn't accuracy. It's whether it reveals something
you couldn't see without it. Composition-as-search-depth is invisible from
inside either practice. Creative death as unsatisfiability is invisible
without tracking constraint accumulation. The Pareto frontier is invisible
without naming competing objectives. None of this tells Harris how to write
better songs. He's been solving these constraints for fifty years and his
weights are better than any model's.

But it tells you where to look when the solver stalls: which constraint to
relax, which dimension to expand, which depth to change.

The geometry is a map. The songwriter is the territory.

---

🦬☀️ *Cross-domain observation from the [warp-core](../../research/warp-core.md) FPGA project,
[warp-types](../../research/warp-types.md) GPU type system, and
[warp-types-sat](https://crates.io/crates/warp-types-sat) constraint solver.
Previously: [Compose From the Bass](../../04/compose-from-the-bass/) and
[The Constraint You Already Had](../../05/the-constraint-you-already-had/).
[GitHub](https://github.com/modelmiser).*
