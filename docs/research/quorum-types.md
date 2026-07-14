# quorum-types

A distributed-systems generalization of warp-types: type-level epochs make
split-brain unrepresentable at compile time, with runtime leases where types
cannot reach.

**Status:** Feasibility study — public on GitHub, not published to crates.io.

**Repository:** [github.com/modelmiser/quorum-types](https://github.com/modelmiser/quorum-types)

## What it is

warp-types prevents GPU divergence bugs by encoding a warp's active-lane set in
the type system. A GPU warp is a degenerate best-case distributed system — fixed
membership, lockstep, no partitions, no failure — so warp-types is already a
session/ownership type system specialized to the friendliest distributed system
in existence. quorum-types asks what has to change to handle a real one.

The answer is an arc, each step verified: a configuration **epoch** lifted into
the type makes cross-epoch `merge` a compile error (split-brain unrepresentable
structurally); a bounded TLA+ model shows that guarantee is *necessary but not
sufficient* because split-brain is temporal; a runtime lease supplies the missing
guard; dynamic membership generalizes by *flipping the set relation* (disjoint
complement becomes intersecting quorum); composing the two shows they
partition safety by regime — structural within a configuration, temporal across
one; and finally the same discipline turns on the *values*: a consistency
lattice (`Local` → `At` → `Agreed`) where the only move up consumes a proposal
and demands a quorum as evidence, so a committed value is unforgeable and
"act only on decided values" is a compile error. The same discipline then
extends to *merging* two committed values that disagree — evidence-gated on
the merge function's property-checked semilattice laws (sampled evidence, not
proof) — and the merged result re-enters the lattice at the bottom: a merge
is a new proposal, not a decision. The final rung changes the fault model
itself: when nodes can *lie*, crash evidence becomes a different type, not a
bigger number — a masking quorum (`n ≥ 4f+1`, after Malkhi–Reiter; the famous
`3f+1` assumes signed data) whose certificate will not unify with the crash
one, and whose every guarantee is conditional on an operator-declared fault
budget no type can check.

It is a research feasibility study, not a consensus library: no transport layer,
the formal model is bounded, and the property tests cover small domains.

## Blog posts

<!-- blog-posts:quorum-types:6 -->

## Links

- [github.com/modelmiser/quorum-types](https://github.com/modelmiser/quorum-types)
