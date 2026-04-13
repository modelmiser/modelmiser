---
date: 2026-04-13
categories:
  - warp-types
---

# One Oracle, Four Products

A SAT solver answers one question: is this set of clauses satisfiable? Four crates — the solver itself, a bounded model checker, an SMT solver, and a property-directed reachability engine — are built on that question, each posing it differently.

<!-- more -->

## The oracle

`solve_watched_budget` takes a clause database, a variable count, and a conflict budget. It returns SAT (with an assignment), UNSAT, or Unknown (budget exceeded). The CDCL engine inside — watched literals, VSIDS, Luby restarts, 1-UIP conflict analysis — spans several thousand lines. But from the outside, it's a black box that answers yes-or-no questions about Boolean formulas.

The SAT solver is both a standalone product (it ships a `solve` binary for DIMACS files) and the oracle for the other three crates. Each routes through the same CDCL core. None touches the solver's internals. The only thing that varies is how the question is posed.

## Four encodings

**SAT** itself answers the raw question: given clauses, satisfiable or not? Users feed it DIMACS CNF files; it returns an assignment or UNSAT. One call, one answer. The interesting part isn't what SAT does — it's what the other three build on top of it.

**BMC** (bounded model checking) asks: "can the system reach a bad state in *k* steps?" It unrolls the transition relation *k* times — each step creates fresh variables for the next time frame, with clauses encoding how the current state determines the next. The property is negated at the current depth via Tseitin encoding. One SAT call per depth. If UNSAT, the system is safe at that depth; deepen and try again. If SAT, the assignment directly encodes the counterexample trace — read off the state variables at each time frame.

**SMT** (satisfiability modulo theories) asks a subtler question: "is this formula satisfiable under the theory of equality with uninterpreted functions?" The formula `a = b AND f(a) != f(b)` looks satisfiable to a pure SAT solver — the propositional variables for `(a = b)` and `(f(a) = f(b))` are independent Booleans. The theory knows they aren't. SMT works by Tseitin-encoding the Boolean structure into clauses (the propositional skeleton), then plugging a theory solver into the CDCL loop via three callbacks: check consistency after each propagation fixpoint, backtrack when the solver backtracks, and lazily explain theory-propagated literals during conflict analysis. The SAT solver explores a Boolean abstraction; the theory solver refines it.

**PDR** (property-directed reachability) asks the question BMC cannot: "is the system safe at *all* depths?" It makes dozens of SAT calls per frame — checking whether bad states exist in the current overapproximation, whether a bad state has a predecessor, whether a blocking clause generalizes — each a fresh clause database built from the frame's clauses plus the transition relation. Where BMC makes one expensive call per depth, PDR makes many cheap ones. The payoff: when PDR succeeds, it has found an inductive invariant, a proof that holds forever.

## What changes at the interface

The four products exercise the oracle in qualitatively different ways:

| Product | Calls per run | Variables per call | What the model encodes |
|---------|---------------|-------------------|---------------------|
| SAT     | 1             | Formula-sized      | Variable assignment  |
| BMC     | 1 per depth   | O(depth × state)   | Counterexample trace |
| SMT     | 1 (internally many) | Formula + Tseitin | Theory-consistent assignment |
| PDR     | Dozens per frame | 2 × state vars   | Predecessor state / blocked cube |

BMC's SAT instances grow linearly with depth — at depth 100 with 1000 state variables, the instance has 100,000 variables. PDR's instances stay small (twice the state variable count) but there are many of them. SMT makes exactly one call to `solve_with_theory`, but inside that call the CDCL loop invokes the theory solver after every propagation fixpoint — it's the tightest integration, a callback protocol rather than a batch query.

The `TheorySolver` trait is the narrowest interface: three methods, twenty lines of API surface. `check` returns Consistent, Propagate, or Conflict. `backtrack` retracts theory state. `explain` lazily produces reason clauses. The SAT solver doesn't know what "equality" means; the EUF engine doesn't know about Boolean reasoning. They compose through this protocol.

## The bug that taught the lesson

During development of the PDR crate — before the first commit — the IC3 engine ran an infinite loop on even trivial systems. The cause was a formulation mismatch in the counterexample-to-induction search.

There are two standard formulations. Bradley's IC3 checks `F_k AND NOT P` — "is there a bad state in the current frame?" Een-Mishchenko-Brayton's PDR checks `F_k AND T AND NOT P'` — "is there a state whose successor is bad?" Both are correct algorithms. The difference is what blocking does.

When you block a cube `c` by adding `NOT c` to frame F_k, Bradley's formulation benefits immediately: the query `F_k AND NOT P` now contradicts `c AND NOT P` for any cube contained in `c`. The blocked cube cannot return.

With the transition-based formulation, `NOT c` constrains current-state variables, but the query checks next-state violations. A different current state can still transition to the same bad next state. The "blocked" cube returns via a new predecessor. Blocking targets dimension X; the query checks dimension Y. The loop never terminates.

The fix was changing one function — `find_cti` — from transition-based to state-based. Seven lines of encoding. The rest of the engine was correct.

The general principle: when an algorithm has a block-and-recheck loop, the blocking mechanism must operate in the same query space as the recheck. If they're in different spaces, blocking is a no-op and the loop diverges. In CDCL solving, this is obvious — learned clauses constrain the same variable space the solver searches. In IC3, it's easy to get wrong because there are two variable spaces (current-state and next-state) and the encoding chooses which one blocking targets.

## Where the abstraction leaks

The one-oracle architecture has real costs.

**PDR rebuilds the clause database per query.** Each consecution check, predecessor query, and generalization attempt creates a fresh `ClauseDb` and calls the solver from scratch. A production IC3 implementation would use incremental SAT — assumption literals that let you add and retract clauses without rebuilding. The warp-types SAT solver doesn't expose assumption literals, so PDR pays the full initialization cost per query. For small transition systems this is negligible. For a 10,000-variable industrial model with hundreds of frame clauses, it would dominate runtime.

**SMT's callback protocol adds per-fixpoint overhead.** The `TheorySolver::check` method is called after every BCP fixpoint — potentially thousands of times per SAT call. Each invocation scans the trail for new theory-relevant assignments, runs congruence closure, and checks disequalities. The alternative (tighter integration where the theory solver shares data structures with BCP) would be faster but would destroy the clean interface. Z3 and CVC5 chose the tighter path. This stack chose the interface.

**The conflict budget is a blunt instrument.** BMC uses it as a timeout: one long call, bail out if it takes too long. PDR needs something different — many fast calls where "fast" means "fail quickly if the instance is hard." The same budget parameter means different things in different contexts, and tuning it requires knowing which product is calling.

These are real limitations, not future work. They're the price of composability — the oracle knows nothing about its callers, and that ignorance is both the feature and the cost.

---

🦬☀️ *warp-types is a verification stack: SAT, BMC, SMT (QF_EUF), and PDR — four crates, one oracle. All on [crates.io](https://crates.io/crates/warp-types-sat). [GitHub](https://github.com/modelmiser/warp-types).*
