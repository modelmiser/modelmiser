---
date: 2026-04-05
categories:
  - crossdomain
---

# The Constraint You Already Had

When the correctness machinery turns out to be the scheduling machinery.

<!-- more -->

The [previous post](../../04/compose-from-the-bass/) argued that composing FROM
the binding constraint produces designs unreachable by iterative optimization.
This post argues that sometimes the binding constraint is hiding inside
something you already built.

## The problem nobody solves on GPU

Conflict-Driven Clause Learning is the algorithm behind every serious SAT
solver. It works by making speculative variable assignments, propagating
their consequences through a clause database, and when a contradiction
appears, analyzing the conflict to learn a new clause that prevents the same
mistake. Then it backtracks and tries again.

The loop is: Decide → Propagate → Conflict → Analyze → Backtrack →
Propagate → ... until every variable is assigned (satisfiable) or the
search space is exhausted (unsatisfiable).

GPU researchers have tried to parallelize this for fifteen years. The track
record is poor: most successful GPU SAT systems offload specific subtasks
— clause simplification, BCP, database management — while keeping the CDCL
control loop on CPU. Full GPU-native CDCL remains an open problem. The reason
is straightforward: CDCL's state machine has strict phase ordering
requirements, and violating them produces silent corruption.

The specific failure mode: two threads propagating the same clause
simultaneously, producing contradictory learned clauses that corrupt the
solver's knowledge base. Every existing parallel solver prevents this with
runtime locks or atomic flags. On GPU, where thousands of threads share a
clause database, the locking overhead kills the parallelism advantage.

## What someone said about warp-types

[warp-types](../../research/warp-types.md) is a Rust crate that encodes GPU
warp semantics in the type system. Its `Warp<S>` type carries a
compile-time `ActiveSet` that tracks which lanes are live. You can't shuffle
data from an inactive lane — the compiler rejects it. You can't use a warp
token in two places — it's non-Copy. The guarantee is static: zero runtime
cost, checked entirely before the code runs.

A reasonable first reaction: it solves correctness, not performance. It
doesn't help GPU SAT.

They were thinking guitar-first. The question they asked was: "how do I make
CDCL faster on GPU?" And a type system that prevents lane-access bugs doesn't
answer that question.

The question they didn't ask: what if the type system that prevents
lane-access bugs also prevents clause-assignment bugs — and those are the
same kind of bug?

## The same trick twice

A `Warp<S>` token is non-Copy. Holding one proves you have exclusive access
to a warp's active set. You can't clone it and use it in two places — the
compiler prevents this structurally.

A clause ownership token can work the same way:

```rust
/// Holding a ClauseToken proves exclusive access to that clause.
/// Non-Copy, non-Clone — double-assignment is a compile error.
#[must_use]
pub struct ClauseToken {
    index: usize,
}

// Deliberately NOT deriving Copy or Clone.
```

Two threads propagating the same clause is the #1 bug in parallel SAT. With
`ClauseToken`, it's not a bug you test for or a race condition you lock
against. It's a program that doesn't compile. The same mechanism that
prevents "shuffle from inactive lane" prevents "propagate an already-claimed
clause" — because both are affine ownership violations.

This wasn't visible from the performance direction. If you start from "how
do I parallelize CDCL?" you reach for locks, atomics, work-stealing queues.
You never reach for a type system. But if you start from the constraint
— "what does affine ownership prevent?" — you discover that it prevents a
class of bugs that includes both GPU lane errors and SAT scheduling errors.

The correctness machinery IS the scheduling machinery. They're not in a
hierarchy. They're structurally analogous — the same ownership discipline
applied at two different levels.

## Phase types as the second layer

Affine clause tokens prevent double-assignment. But CDCL has a second
correctness requirement: phase ordering. You must propagate after
backtracking. You must analyze before backtracking. You must not decide
during propagation. Violating any of these produces corrupt solver state.

warp-types already had a pattern for this. Its fence module uses zero-sized
marker types to track write phases: `Unwritten → PartialWrite → FullWrite →
Fenced`. Each transition consumes the old state and produces the new one. The
compiler enforces ordering.

The CDCL state machine is the same pattern, one level up:

```rust
/// Zero-sized marker types — no runtime cost.
pub struct Idle;
pub struct Decide;
pub struct Propagate;
pub struct Conflict;
pub struct Analyze;
pub struct Backtrack;

/// Session tracks the current phase at compile time.
/// Transitions consume the session, produce the next phase.
pub struct SolverSession<P: Phase> { /* zero-sized */ }

impl SolverSession<Backtrack> {
    /// CDCL requires propagating the learned clause immediately.
    /// This is the ONLY transition out of Backtrack (besides unsat).
    pub fn propagate(self) -> SolverSession<Propagate> { /* ... */ }
}
```

`Backtrack → Propagate` is the only valid transition. `Backtrack → Decide`
is a compile error. Not a runtime check, not an assertion — a type error.
Without the type system, a missing `Backtrack → Propagate` enforcement
would produce silently wrong SAT results — and the bug would be invisible
in code review because the control flow *looks* correct.

## Water hammer

In fluid dynamics, water hammer occurs when you close a valve while fluid is
still flowing. The momentum has nowhere to go. The pressure spike can burst
pipes.

Phase ordering bugs in CDCL are water hammer. Propagating before backtracking
completes means asserting new consequences while the old, contradicted
consequences are still in the trail. The learned clause hasn't been retracted
yet. The solver's knowledge base contains both "X is true (from propagation)"
and "X caused a contradiction (from analysis)" simultaneously. The pressure
spike — contradictory learned clauses — corrupts the solver permanently.

The type system is the physical interlock that prevents closing the valve
while flow is in progress. `Backtrack` has one exit: `propagate()`. You can't call
`decide()` from `Backtrack` because the method doesn't exist on that type.
The phase ordering is baked into the type structure.

## What Part 1 didn't cover

The previous post's thesis — compose FROM the binding constraint — assumes
you know which constraint is binding. Harris knows he's holding a bass. The
roofline model tells you whether you're memory-bound or compute-bound. The
principle works when the constraint is identifiable.

Constraint unification is different. The insight isn't "compose from the
type system instead of from performance." The insight is that the type system
you built for correctness and the scheduling system you need for parallelism
are the same system viewed from different angles. You don't change which
instrument leads — you discover one instrument was playing two parts.

This suggests an architectural possibility worth noting, even if it's
speculative: phase types don't care whether `Propagate` runs on GPU, FPGA,
or CPU. The type contract — "you must be in Propagate phase to run BCP, and
Propagate can only follow Decide or Backtrack" — is substrate-agnostic. A
GPU tile checking clauses via ballot, an FPGA pipeline doing unit propagation
in hardware, and a CPU running conflict analysis could in principle
participate in the same CDCL session, coordinated by the same phase types.

Nobody has built a GPU+FPGA+CPU hybrid CDCL solver. Whether phase types are
sufficient to make that tractable is an open question. But they do reduce the
integration problem from "ensure phase ordering holds at runtime across three
substrates" to "ensure each substrate's entry points are typed correctly" —
and the compiler checks the latter.

## The general case

Not every project has a hidden constraint unification waiting to be found.
But the pattern is worth watching for: any time you've built a correctness
mechanism that uses affine types, linear types, or typestate, ask whether the
class of bugs it prevents is broader than the class you designed it for.
Ownership tracking prevents use-after-free. It also prevents
double-assignment. It also prevents phase-ordering violations. These aren't
analogies — they're the same mechanism at the type level.

The instrument you're holding might already be playing two parts. The
question is whether you've noticed.

---

🦬☀️ *[warp-types](../../research/warp-types.md) is a type-safe GPU warp library
on [crates.io](https://crates.io/crates/warp-types).
[warp-types-sat](https://crates.io/crates/warp-types-sat) extends it to SAT solving.
[GitHub](https://github.com/modelmiser/warp-types).*
