---
date: 2026-04-13 14:00:00
categories:
  - warp-types
---

# Neither Theory Alone

An SMT solver with one theory is a SAT solver with opinions. Add a second theory and you need a protocol for disagreement.

<!-- more -->

## The gap

The [previous post](../one-oracle-four-products/) described four products built on a single SAT oracle. The SMT solver was one of them — it plugs an EUF (equality with uninterpreted functions) engine into the CDCL loop via three callbacks: check, backtrack, explain. Twenty lines of trait surface.

That surface carries more weight than it seems. Consider this formula:

```text
x = 3  AND  y = 4  AND  f(bvadd(x, 1)) != f(y)
```

EUF knows about congruence: if `a = b` then `f(a) = f(b)`. It knows nothing about bitvectors. The term `bvadd(x, 1)` is a black box — it could equal anything.

A bitvector theory knows that `bvadd(3, 1) = 4`. It knows nothing about uninterpreted functions. The term `f(...)` is a black box.

Neither theory alone can determine that the formula is unsatisfiable. EUF needs to know `bvadd(x, 1) = y` to fire congruence on `f`. BV needs EUF's equalities `x = 3` and `y = 4` to evaluate the addition. The reasoning crosses the theory boundary.

## Nelson-Oppen in thirty seconds

The standard answer is Nelson-Oppen combination (1979): run both theories, share equalities between them, repeat until they agree or one detects a conflict.

The textbook version has a loop inside the combining solver. Theory A discovers `a = b`, shares it with Theory B. Theory B discovers `c = d`, shares it back. Repeat until fixpoint.

We don't have that loop. The SAT solver already runs one.

## The BCP loop is the sharing loop

After each BCP fixpoint, the SAT solver calls `theory.check()`. If the theory propagates a literal, the solver records it on the trail, re-runs BCP, and calls `check()` again. This is the equality sharing loop — it's just driven by the SAT solver rather than by the combiner.

The `CombiningSolver` wraps EUF and a theory module behind a single `TheorySolver` interface. On each `check()` call:

1. EUF processes the trail. If it finds a conflict or propagation, return it immediately.
2. Once EUF is at fixpoint, share trail equalities to the BV module.
3. Ask BV for new equalities.
4. If BV discovered something, propagate it to the SAT solver.

Step 4 doesn't merge the equality into EUF. It tells the SAT solver, which records it on the trail. On the next `check()`, EUF sees it and processes it normally. The combining solver never touches EUF's union-find. The fixpoint emerges from the existing control flow.

```text
SAT solver (CDCL)
    |  check / backtrack / explain
    v
CombiningSolver
    |-- EufSolver  -- congruence closure, trail scanning
    |-- BvSolver   -- constant propagation, ground evaluation
    '-- equality sharing via DPLL(T) BCP loop
```

## The demo

```text
-- Example 5: x = 3, y = 4, bvadd(x,1) != y --
  EUF only: SAT
  EUF + BV: UNSAT

-- Example 6: x = 3, y = 4, f(bvadd(x,1)) != f(y) --
  EUF only: SAT
  EUF + BV: UNSAT
```

Example 5 is the direct conflict: BV evaluates `bvadd(3, 1) = 4 = y`, contradicting the disequality. Example 6 is the cascade: BV discovers `bvadd(x, 1) = y`, propagates it through the SAT solver to EUF, EUF fires congruence on `f`, conflict. Two theories, one BCP loop, zero internal fixpoint machinery.

## The soundness bug

The first version of the combining solver explained module propagations as unit clauses. When the BV module said `bvadd(x, 1) = y`, the `explain()` callback returned `[bvadd(x,1) = y]` — a one-literal clause asserting the equality unconditionally.

This is correct for axioms (equalities that hold in every model of the theory). It is unsound for conditional equalities.

`bvadd(x, 1) = y` holds because `x = 3` and `y = 4`. If the SAT solver backtracks those assignments — deciding to try `x != 3` — the equality no longer follows. But the unit clause is already learned. The solver would force `bvadd(x, 1) = y` even in a branch where `x` is 7 and `bvadd(7, 1) = 8 != 4`.

The fix: every equality reported by a theory module carries its premises — the trail atoms that the deduction depends on.

```rust
pub struct ModuleEquality {
    pub t1: TermId,
    pub t2: TermId,
    pub premises: Vec<(TermId, TermId)>,
}
```

The BV module tracks *why* each term has its known value through a `ValueReason` chain: `Constant` (inherent, no premise), `Equality(t1, t2)` (propagated from a trail atom), or `Evaluation` (computed from arguments — recurse into their reasons). Collecting premises walks this DAG:

- `bvadd(x, 1)` has value 4 because of `Evaluation`. Its arguments: `x` (value 3 via `Equality(x, bvconst_3)`) and `bvconst(1)` (value 1 via `Constant`).
- `y` has value 4 via `Equality(y, bvconst_4)`.

Premises: `{(x, bvconst_3), (y, bvconst_4)}`. The conflict clause becomes:

```text
NOT(x = 3)  OR  NOT(y = 4)  OR  (bvadd(x,1) = y)
```

All three literals are false on the trail. The clause is valid — it's a theory lemma the SAT solver can learn from, backtrack correctly, and never misapply.

## Dormant atoms

There's one more piece. The formula `f(bvadd(x, 1)) != f(y)` creates an equality atom for `(f(bvadd(x,1)), f(y))` via the Neq encoding. But the BV module discovers `bvadd(x, 1) = y` — and there's no atom for that pair. The combining solver communicates through atoms. No atom, no channel.

The fix is argument pair purification. After Tseitin encoding, the formula abstraction layer scans all equality atoms. If both sides are function applications with the same function symbol — like `f(bvadd(x,1))` and `f(y)` — it creates atoms for their argument pairs. `(f(a), f(b))` implies we might need `(a, b)`.

The new atoms are unconstrained by any clause. The SAT solver can assign them freely. They sit dormant until a theory module discovers the corresponding equality, at which point the combining solver propagates through them. For pure EUF formulas, they're noise the solver ignores. For cross-theory formulas, they're load-bearing.

This iterates to fixpoint for nested applications: `(g(f(a)), g(f(b)))` creates `(f(a), f(b))`, which creates `(a, b)`. In practice, one or two iterations suffice.

## What the abstraction costs

The combining solver adds per-check overhead: trail scanning for the module, one `propagate()` call, atom lookup for each discovered equality. When the module is `NullModule` (the zero-cost default), the compiler eliminates all of this — the monomorphized code is identical to bare EUF.

With a real module, the cost is proportional to the number of BV terms and the frequency of theory-check calls. The BV module's constant propagation is O(BV ops) per check, not O(formula size). For GPU lane-index formulas — dozens of 5-bit arithmetic terms, not thousands — this is negligible.

The real cost is incompleteness. The BV module evaluates ground expressions (all arguments have concrete values). It doesn't do symbolic reasoning — `bvadd(x, 1) = bvadd(y, 1)` when `x = y` requires either bit-blasting or BV-aware congruence, neither of which we've built. The `TheoryModule` trait is ready for a richer solver; the current one handles the cases where constants flow through arithmetic, which is the common pattern in warp-index formulas.

## The twenty lines

The `TheoryModule` trait has five methods:

```rust
fn notify_equality(&mut self, t1: TermId, t2: TermId);
fn notify_disequality(&mut self, t1: TermId, t2: TermId);
fn propagate(&mut self) -> ModuleResult;
fn push_level(&mut self);
fn backtrack(&mut self, level: u32);
```

The combining solver handles trail dispatch, atom lookup, conflict clause construction, explanation, and backtrack coordination. A new theory implements those five methods and plugs in. The SAT solver never knows it's there.

The `TheorySolver` trait from the previous post was twenty lines facing the SAT solver. The `TheoryModule` trait is twenty lines facing the theory. Between them, the combining solver — about 150 lines of routing — lets a second theory compose with EUF through the same BCP loop that drives the CDCL core.

Two narrow interfaces. One loop. Neither theory alone.

---

🦬☀️ *warp-types-smt is MIT-licensed. [GitHub](https://github.com/modelmiser/warp-types).*
