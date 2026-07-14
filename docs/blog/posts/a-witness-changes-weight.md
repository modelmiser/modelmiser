---
date: 2026-07-13 05:00:00
categories:
  - quorum-types
---

# A Witness Changes Weight

The value lattice commits a value and throws its quorum witness away. Under nodes that lie, that same witness becomes the only thing holding the value up.

<!-- more -->

## The argument an underscore was making

This is the eighth post on quorum-types, a feasibility study asking whether the compile-time safety of [warp-types](what-the-type-erases-to.md) survives the move to a distributed system; the series climbs one ladder, a rung per result. Two earlier rungs bracket this one. The [value lattice](up-is-gated-down-is-free.md) typed a value's consensus strength — a `Local` proposal moves *up* to a committed `At<T, E>` only when a quorum witnesses it, and down for free. The [Byzantine rung](the-famous-number-assumes-a-signature.md) typed the quorum itself for nodes that lie — a masking quorum whose certificate is a distinct type, carrying a declared fault budget `f`. Set the two side by side and something is missing between them.

Here is the up-move from the value lattice, verbatim:

```rust
pub fn commit<const E: u64>(self, _witness: &Quorum<E>) -> At<T, E> {
    At { value: self.value }
}
```

Look at the witness. It is `_witness` — bound with a leading underscore, the Rust convention for *I take this argument and use nothing about it*. The function stamps `self.value` as committed and never inspects the quorum. That is not sloppiness; it is exactly right under crash faults. A `Quorum<E>` is proof that a majority of the configuration at epoch `E` exists, and under the crash model a majority is honest by assumption. If an honest majority stands behind you, the value you are holding *is* the agreed one — the quorum's mere existence is the whole guarantee, and there is nothing to check about the value it agreed to. The witness can be discarded because honesty already did its job.

The Byzantine rung types who may be believed. The value lattice types how strongly a value is held. Neither types the join: *a value that is believable because the right nodes vouched for it under faults that include lying.* That is the join this rung types — who may be believed, welded to what they said — and the underscore is where its absence shows.

Because the moment a minority can lie, `commit`'s move is unsound. A single Byzantine node hands you a fabricated value and a plausible-looking witness, and `commit` stamps the forgery. The fix is not a runtime check bolted onto `commit`. The fix is that the witness must change weight — it has to become load-bearing, the thing that decides *which* value is believable, not decoration on a value the caller already chose.

## A value with no way in

Before any code existed, the pre-registration wrote down how this rung could die. Two of those ways are about that weight change. One: `attest` compiles while ignoring what the votes carry — in which case the Byzantine value tier is the crash tier relabeled, and the rung adds nothing. The other: the votes argument turns out to be discardable, an `_votes` the way `commit` had an `_witness` — same collapse, different underscore.

Both die by construction, in the shape of one signature:

```rust
pub fn attest<T: Eq, const E: u64>(
    votes: Vec<Vote<T, E>>,
    cfg: &BftConfig<E>,
) -> Option<Attested<T, E>>
```

There is no `value: T` parameter. The caller cannot supply the value to be attested — the function *extracts* it from the votes, minting an `Attested<T, E>` only when some value was cast by `f+1` distinct members of `cfg`. And `Attested` has a private field and no public constructor. Those two facts compose into something stronger than a check: a value can inhabit an `Attested<T, E>` only if `f+1` votes carried it, because that is the only door, and the door has no other way to produce a `T`. Ignore the votes and there is no value left to return. The underscore `commit` writes on its witness is not a style choice you could repeat here — it is unwritable. Value-blindness is not guarded against; it is unrepresentable.

Two compile-fail doctests hold that line. One tries to construct an `Attested` directly and cannot reach the private field. The other offers a vote minted at epoch four to a configuration at epoch three, and the const generic `E` refuses to unify — the same cross-epoch type error the [first rung](split-brain-unrepresentable.md) built the whole crate on, reaching one layer further out, to the votes.

Why `f+1`? Because `f` liars can, between them, produce at most `f` matching votes for a fabrication. The `(f+1)`-th vote must come from someone outside the fault budget — a correct node. So `f+1` distinct votes for a value guarantee at least one honest witness to it, and the value was therefore not conjured by the liars alone. That pigeonhole — `f+1` distinct votes force one honest voucher — buys a specific, limited thing: existence. (No signatures are involved; a vote is just a matching value, in keeping with this crate's [signature-free stance](the-famous-number-assumes-a-signature.md).)

## Existence is not uniqueness

Existence is not uniqueness — and that gap is another pre-registered falsifier, the one that fired.

Count it out with the crate's smallest legal configuration: five members, fault budget one, so the existence threshold is `f+1 = 2`. An equivocating node — call it node 4, the one liar the budget allows — tells one collector the value is `A` and another that it is `B`. Give each collector one honest ally: node 0 also votes `A`, node 1 also votes `B`. Now the first collector has `A` from `{0, 4}` and the second has `B` from `{1, 4}`. Two distinct votes each. Both clear `f+1`. Both attest.

Two `Attested` values, `A` and `B`, at the same epoch, each with a genuine honest voucher. Existence held for both — neither was fabricated by the liar alone — and existence was never uniqueness. A passing test records exactly this, node 4 sitting in both support sets, which is what equivocation *is*.

This is not a bug in the tier; it is the tier's boundary, surfaced rather than hidden. `f+1` is honest about what it delivers: *this value was seen by someone correct.* It makes no claim that it is the only such value. The pre-registration predicted this falsifier would fire "as a refinement, not a collapse," and it did — it split the rung in two. Existence is `attest`. Uniqueness is a second tier, at a higher threshold, and it needs a different piece of machinery — one the Byzantine rung already built.

## The threshold that forbids two answers

Uniqueness lives at the *masking* threshold: `⌈(n + 2f + 1) / 2⌉`, which for five members and one fault is `⌈8/2⌉ = 4`. A second constructor, `commit_masking`, takes a masking quorum's worth of distinct votes for one value and mints a `Committed<T, E>`, carrying a `ByzQuorum<E>` — the certified masking quorum from the [Byzantine rung](the-famous-number-assumes-a-signature.md) — as its support.

Why four denies what two allowed: any two subsets of size four drawn from five members overlap in at least `2·4 − 5 = 3` members. Three is `2f + 1`, and of any `2f + 1` members at most `f` can be liars, so at least `f + 1 = 2` are correct. Two masking quorums for two *different* values would therefore share at least two correct members — and a correct member does not vote for two different values. Contradiction. One equivocating liar plus a minority can reach `f+1`; it cannot reach four for a second value without conscripting correct nodes into voting twice, which the fault model forbids.

That impossibility is the construction-time bar, and `commit_masking` is where it bites: a second, conflicting value's votes never reach four, so the constructor returns `None` and the conflicting `Committed` is simply never built. The intersection behind the bar is also available as a typed witness after the fact:

```rust
pub fn agreement_witness(&self, other: &Committed<T, E>) -> Option<Overlap<E>> {
    self.quorum.intersect(other.quorum())
}
```

`intersect` is the Byzantine rung's own operation: it takes two masking quorums and returns an `Overlap` only when they meet above `2f`, and the `Overlap` reports its minimum correct membership — `≥ f+1`. Handed two `Committed` values that both got built at one epoch, `agreement_witness` exhibits the correct vouchers they share — and those vouchers, each having voted once, are why the two values must already be equal. The uniqueness reduces to intersection, exactly as the classic PBFT safety argument does, but it holds in ordinary Rust with no external prover: enforced by the constructor when the value is built, and made inspectable by this method afterward. This is the value-level twin of the [first rung's](split-brain-unrepresentable.md) split-brain-unrepresentable result, with one asymmetry the fencing section returns to: there, two stale halves of different epochs cannot typecheck a merge; here, two committed values of one epoch cannot be *constructed* from disjoint honest quorums.

## One liar, two thresholds

The cleanest way to test a sign-flip is to hold the adversary fixed and change only the threshold. The [wire rung](the-wire-is-where-const-generics-die.md) gave the toy a deterministic network under [turmoil](https://github.com/tokio-rs/turmoil), and its discipline carries over intact: votes arrive as 25-byte datagrams, and a single `promote_vote` function is the sole crossing from bytes to a typed `Vote`, checking the node id fits and — the wire rung's lesson — that the epoch *matches* the collector's compiled `E` rather than being lifted into it. A const generic still cannot come off a socket.

The scenario runs one equivocating host against two collectors, partitioned from each other so their two views cannot reconcile — the gap the equivocation lives in. The honest nodes split their votes; node 4 tells the two collectors different values. Then the same network trace is read twice, once by each threshold.

At the existence threshold, the liar wins. This is the negative control: it must have teeth, or the positive result below proves nothing. The two decision lines, with the harness's split-violation record appended:

```text
t=4 collector-b decided v0xbb
t=4 collector-a decided v0xaa
t=4 value-split: collector-b=v0xbb vs collector-a=v0xaa
```

At the masking threshold, the *same host under the same schedule* is denied:

```text
t=4 collector-b committed nothing
t=4 collector-a committed nothing
```

Neither minority value reaches four; both collectors abstain; no split is possible. Safety here is not "nothing bad happened to be scheduled" — the existence twin proves the schedule has teeth — it is "the bad outcome could not clear the bar." And to keep the masking result from passing vacuously (a tier that only ever abstains would be trivially safe, the [vacuity failure mode](a-merge-is-a-proposal.md) this series keeps hunting), a third scenario gives four honest nodes the same value: both partitioned views commit it, they agree, and the liar's forged alternative never commits. The threshold that denies the split also delivers a decision.

## Fencing the claims

The algorithm here is old and I claim none of it. The `f+1`-forces-one-honest pigeonhole is Byzantine-agreement folklore; uniqueness-by-quorum-intersection is the founding masking-quorum result — Malkhi and Reiter's Byzantine quorum systems (1998), and the safety argument of Castro and Liskov's PBFT (1999). What is worth stating precisely is where the *encoding* sits relative to work that has typed or verified these ideas before.

Verified distributed systems prove arguments like this one — in a proof assistant. Velisarios (ESOP 2018) machine-checks PBFT's Byzantine safety in Coq, quorum intersection and all — the same argument this rung makes, discharged as a mechanized lemma in an external prover (IronFleet's Dafny-checked crash-fault Paxos and Verus's SMT-checked Rust are adjacent neighbors in that space). This toy's move is smaller and different in kind: the same reduction holds in ordinary Rust at construction time, no SMT, no external checker — a smart constructor whose success *is* the certificate. The nearest type-theory neighbor is Recalling a Witness (POPL 2018), which gives F\* a first-class `witnessed` token certifying that a stable predicate held over monotonically-evolving state; this rung generalizes that witness-as-a-type move from stable state to a Byzantine quorum. The crash-discardable, Byzantine-load-bearing contrast that frames this post — the underscore that cannot survive the fault-model change — I could not find stated as a result anywhere, which makes it fresh framing rather than a claimed theorem.

And the fence on the artifact. The honesty that matters most is where the type stops: two *conflicting* `Committed` values are prevented by `commit_masking` returning `None` for the second — when no second value's votes reach the masking threshold — not by a compile error. `agreement_witness` only exhibits agreement after the fact, once two commits already exist; it does not make disagreement fail to typecheck. Doing that would require lifting values, not just epochs, to the type level — value-level branding — and that runs straight into the wall the [wire rung](the-wire-is-where-const-generics-die.md) already mapped: Rust has no `TestEquality`, no way to recover a type-level equality witness from two runtime values that happen to match. The guarantee is real and it is discharged at the constructor. It is not discharged at `typeck`, and saying otherwise would be the overclaim this post exists to avoid.

## What the rung measured

Down the ladder, the evidence has been weakening in a documented pattern: a counted majority, then a sampled law (the [reconciliation rung's](a-merge-is-a-proposal.md) property-checked merge, evidence not proof), then a counted supermajority conditional on a declared budget, then the same majority again with its provenance demoted to bytes off a wire. This rung adds a distinction orthogonal to that decay — not weaker evidence, but a different question. The earlier rungs asked *who* may be believed. This one asks *what* they said, and answers with a value you cannot hold without corroboration and cannot hold two of at the masking threshold.

The finding fits in the underscore. `commit(self, _witness: &Quorum<E>)` throws its witness away because under crash faults an honest majority's existence is the whole story. `attest` cannot be written that way, and `commit_masking` even less so, because under faults that include lying the witness is not evidence *about* the value — it *is* the value's only claim to being real. A crash-model quorum is a fact you can discard once you've noted it exists. A Byzantine quorum is load-bearing, and the type makes you carry it. Seven rungs bought the chain that reaches this one; the eighth is where the witness stops being something you can throw away and starts being something you hold up.

---

🦬☀️ *quorum-types is a feasibility study — a distributed-systems generalization of warp-types. [GitHub](https://github.com/modelmiser/quorum-types).*
