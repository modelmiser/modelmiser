---
date: 2026-07-13 07:00:00
categories:
  - quorum-types
---

# The Famous Number Assumes a Signature

Every rung of this series assumed nodes fail by stopping. Let them lie, and the evidence has to change type — not size. Along the way, the best-known constant in Byzantine fault tolerance turns out to be licensed by an assumption this toy doesn't get to make.

<!-- more -->

## The point where the old reasoning collapses

This is the sixth post on quorum-types, a feasibility study asking whether the compile-time safety of [warp-types](what-the-type-erases-to.md) — typestates for GPU warps — survives the move to a distributed system. The [second post](disjoint-becomes-intersecting.md) built the crate's membership layer around one arithmetic fact: two majorities of the same configuration must share a member. The safety lemma is a method, `intersect`, returning a shared node, and the whole chain of reasoning that follows — continuity across quorums, no two groups committing independently — hangs on that single shared member.

It also hangs on something the code never states: *the shared member tells the truth*. Every rung so far — epoch guards, leases, dynamic membership, the consistency lattice, [reconciliation](a-merge-is-a-proposal.md) — models nodes that fail by crashing. A crashed node is silent; a silent node cannot mislead you. The moment a node can fail by *lying*, the crash lemma collapses at exactly one point: the intersection of two majorities might be exactly one node, and that node might be the liar. Everything downstream of `intersect` is then built on a witness whose testimony is worthless.

The tempting fix is quantitative — take a bigger majority, get a bigger overlap. The finding this post reports is that the fix is qualitative: Byzantine evidence is a *different certificate*, with different arithmetic behind it and a different meaning in front of it, and the type system can be made to refuse the substitution. Crash evidence where Byzantine evidence is required is a compile error, not a smaller safety margin.

As with the previous rung, the doubt was written down before the code. Two ways this could have died: the design could degenerate into runtime asserts with no new compile-time distinction — a wrapper with no teeth — or the threshold arithmetic could genuinely require type-level integers that stable Rust doesn't have. Neither happened.

## Two regimes, one assumption

Byzantine quorum systems were worked out by Malkhi and Reiter in the late '90s, and their taxonomy contains the decision this module had to get right. Of its regimes, the two that matter here are distinguished not by the adversary but by *what the data can prove about itself*.

**Dissemination quorums** serve self-verifying data — values that carry their own integrity, the canonical example being digitally signed records. A faulty server can *suppress* a signed value, but it cannot *alter* one without detection. So the intersection of two quorums only needs to contain one correct node: whatever that node relays is checkable on arrival, and one honest relay is enough to propagate the truth. For a threshold system tolerating `f` Byzantine nodes, this regime needs `n ≥ 3f+1` servers with quorums of `⌈(n+f+1)/2⌉`, intersecting in at least `f+1` nodes — at least one of them correct.

**Masking quorums** serve everything else: plain values with no signatures, no self-verification, nothing to check on arrival. Now the reader cannot recognize the truth; it must *out-vote the lies*. The correct, up-to-date nodes in the quorum intersection have to outnumber every liar who might vouch for a fabrication — and the liars are not confined to the intersection; all `f` of them can show up anywhere in the read quorum and vote. That costs more: `n ≥ 4f+1`, quorums of `⌈(n+2f+1)/2⌉`, any two intersecting in at least `2f+1` nodes, of which at least `f+1` are correct — a strict majority over `f` liars, wherever they sit.

Here is why this taxonomy is the post's title. The number everyone knows is `3f+1`. It is the number PBFT made famous — Castro and Liskov call it optimal resiliency for asynchronous Byzantine agreement, citing the classical lower bound — and PBFT as specified signs every message; tellingly, its celebrated MAC-based optimization gives up exactly the third-party verifiability a signature buys, and a companion report re-engineers the algorithm to live without it. It is HotStuff's operating point — a quorum certificate is `2f+1` partial signatures over the same message, combined into one threshold signature, self-verifying by construction. For a quorum system over plain data, the famous number assumes a signature. Agreement protocols do exist that reach `3f+1` without signing anything, but they buy self-verification with extra rounds of echoing — a signature paid in messages.

This toy's values are plain Rust data — a `T` with no cryptography anywhere in the crate. Writing `3f+1` into it would have silently imported a signature scheme the code does not model, and the module would have overclaimed in its first constant. The honest regime for unsigned values is masking, so the module's arithmetic is `4f+1`, and the decision was pre-registered as the design's most falsifiable call before the literature check — which then confirmed it.

## The arithmetic, and its negative control

The masking bound is inclusion–exclusion plus one adversarial observation. Two quorums of size `q` over `n` nodes overlap in at least `2q − n` members. At the masking threshold `q = ⌈(n+2f+1)/2⌉`, the overlap is at least `2f+1`: remove the at-most-`f` faulty members and at least `f+1` correct nodes remain — more than the `f` liars can ever muster. Concretely, the minimum masking clusters run `(n, f)` = (5, 1), (9, 2), (13, 3), with quorum thresholds 4, 7, 10; at the smallest, `n = 5, f = 1`, quorums have 4 members and any two share at least 3.

The module's central test checks precisely the adversarial part. For every configuration up to size 7 at `f = 1`, it enumerates every pair of quorums meeting the masking threshold *and every possible placement of the liars* — each `f`-subset of the whole configuration, not just of the overlap — and asserts the correct members of the overlap still outnumber them. That last quantifier is where a plausible-but-wrong version of this module would cut the corner: it is natural to reason about liars *inside* the intersection, but a fabricated value can be vouched for by faulty nodes anywhere in the quorum, which is exactly why the masking bound is `2f+1` and not `f+1`.

And the claim has its counterexample, in the style this series [keeps returning to](a-merge-is-a-proposal.md): a boundary earns trust by rejecting. The crash-majority threshold fails the same adversary, and the test suite exhibits it. Over five nodes, the crash quorums `{1,2,3}` and `{3,4,5}` are both certifiable majorities, and their intersection is exactly `{3}`. If node 3 is the one liar, the two quorums share no correct member at all — crash evidence, however honestly counted, says nothing once counting is what the adversary attacks. The Byzantine boundary refuses a 3-member subset in the first place: the threshold at `n = 5, f = 1` is 4.

## A certificate that will not unify

The types follow the arithmetic. A `BftConfig<E>` is a configuration at epoch `E` carrying a *declared fault budget* `f`; its constructor rejects any membership that cannot tolerate the budget (`n ≤ 4f` returns `None`). Its `certify` method is the same runtime boundary the [third post](where-structure-ends.md) named the crate's load-bearing pattern: check a subset against the masking threshold once, and mint a typed certificate — `ByzQuorum<E>` — that the rest of the program spends structurally.

The decision that carries the rung is that `ByzQuorum<E>` and the crash-fault `Quorum<E>` are *unrelated types*. No trait unifies them; neither converts into the other. An API that needs to survive liars says so in its signature, and handing it a counted majority — however large — fails to typecheck:

```rust
fn read_repair(_evidence: &ByzQuorum<0>) { /* needs masking overlap */ }

let crash_q = Config::<0>::new(members).certify(subset).unwrap();
read_repair(&crash_q);
// error[E0308]: expected `&ByzQuorum<0>`, found `&Quorum<0>`
```

That rejection is the compile error this rung exists to produce, pinned in the test suite the way the [fourth post](up-is-gated-down-is-free.md) established — each `compile_fail` doctest annotated with the specific error it must produce, so a test can't silently pass for the wrong reason. The epoch guard from the rest of the crate carries over unchanged: two `ByzQuorum`s of different configuration generations cannot even be asked whether they overlap, because the `E` parameters do not unify.

One test pins the relationship between the two certificate types from the other side. Set `f = 0` — declare that nobody lies — and the masking threshold `⌈(n+1)/2⌉` collapses, for every nonempty configuration, into exactly the crash majority `⌊n/2⌋+1`. The crash membership module is the `f = 0` fiber of the Byzantine one. The two certificates are not rivals; one is a slice of the other's parameter space, which is why they can share an epoch discipline while refusing to substitute for each other.

That fiber cuts both ways, and the signature's guarantee must be stated exactly: the budget, unlike the fault model, is invisible to it. `ByzQuorum<E>` carries `f` as a runtime field, so a configuration declared at `f = 0` mints certificates that are, semantically, crash majorities wearing the Byzantine type — the same 3-of-5 subset the boundary refuses at `f = 1` walks through at `f = 0`, and an API that wants actual masking strength must still inspect `fault_budget()` at runtime. What the type refuses is the wrong *module*; it cannot demand a nonzero budget. Lifting the threshold choice itself into the parameter list is exactly the move Sui makes below — a move this toy declines: at feasibility scope, the budget stays a field.

## The failure case that would not die

The finding I did not pre-register is what happened to the safety lemma's signature. The crash version is fallible in form — it returns `Option<NodeId>`, even though for quorums of one configuration it always succeeds. The masking threshold makes the overlap's size an arithmetic fact, so the first draft of the Byzantine lemma dropped the `Option` and returned its witness outright: size forced by arithmetic, epoch enforced by the signature, no failure case left to represent.

Safe code refutes that in four lines. The parameter `E` pins the epoch *label*, not the configuration: nothing stops `BftConfig::<0>::new` from being called twice with disjoint memberships, and both configurations then mint perfectly genuine `ByzQuorum<0>`s. Intersect those, and the "guaranteed" overlap is empty — the draft's `min_correct()`, members minus `f`, underflowed — a panic in the test build, a silent wraparound to an absurdly confident number in release — in safe code, under `#![forbid(unsafe_code)]`. The crash module survives the same abuse gracefully, because its `Option` was still there to say *no shared member*. The upgrade to infallibility was precisely where a panic path came in.

So the shipped lemma is fallible again:

```rust
pub fn intersect(&self, other: &ByzQuorum<E>) -> Option<Overlap<E>>
```

— and the round trip bought something, because the failure arm's meaning has sharpened. For two quorums of the same configuration, `None` is unreachable; that is the arithmetic, and the exhaustive test walks it. What `None` actually signals is *epoch-label reuse* — a second configuration wearing the same `E` — and the detection is honest about its own reach: it is one-directional. Reused labels with enough accidental overlap still mint a well-typed witness whose numbers are computed against whichever quorum receives the call — even argument order can change the verdict; the boundary catches the broken promise it can see, not the promise itself. That hole is not a new one; it is the series' oldest. The [fourth post](up-is-gated-down-is-free.md) located the root of trust in `Config::new`: the types prove everything downstream of *a* configuration, and only the operator makes it *the* configuration. The epoch parameter inherits exactly that status — a name the operator promises to use once — and a failure arm whose only remaining job is catching a broken operator promise is that root-of-trust hole made mechanically visible. The failure case cannot be deleted — only moved.

`Overlap<E>` exposes its members and one number, `min_correct()` — the count of members guaranteed correct, at least `f+1`. Guaranteed by what? By the declared budget. Every promise the witness makes is conditional on at most `f` members actually being Byzantine, and `f` is not a measurement — it is an *axiom the operator asserted* when constructing the `BftConfig`. No type checks it; nothing can. If the operator declares `f = 1` and two nodes lie, `min_correct()` returns a confident, well-typed, wrong number.

This is the third appearance of the series' recurring law — types verify chains; operators choose roots. `Config::new` was the first; the [fifth post's](a-merge-is-a-proposal.md) caller-chosen samples, where certification is self-attestation, the second. Here the root is `f` itself: the fault budget is trust, declared, and everything the arithmetic buys is relative to it.

Down the series' ladder, then, the evidence reads: a counted majority (exact, per configuration); a sampled law (probabilistic, per function); and now a counted supermajority *conditional on an unverifiable declaration*. Each rung keeps the discipline — runtime boundary mints witness, types spend it — and each rung's witness means less. The previous post said the ladder trades soundness for reach; this rung shows the trade's conservation law. Uncertainty doesn't shrink when a function's signature gets stronger — it relocates, between the return type and the trust model, and the one design that pretended otherwise panicked. Rung by rung, the thing you must take on faith moves from the mathematics, to the inputs, to the world.

## Who may be believed, not what they said

The scope fence, stated as loudly as the module states it: this rung types the *counting* layer only. A masking overlap tells you at least `f+1` of these particular nodes are correct — *who may be believed*. It says nothing about *what anyone said*. Byzantine nodes also lie about values, and they can tell different lies to different quorums; real read protocols in the masking regime accept a value only when `f+1` members return the *same* one, which requires modeling responses — an attested-value layer this toy deliberately does not have, in the same way it has no wire protocol and no durability. Possessing an `Overlap` proves the arithmetic ran against the declared budget. It does not launder any particular value into truth. Equivocation stays on the far side of the line, uncrossed.

## Fencing the claims

The neighboring work makes the fence easy to draw and worth drawing. Machine-checked Byzantine consensus exists at full protocol scale — Velisarios proved PBFT's safety in Coq — and that is verification of a *protocol*, a different and much heavier undertaking than typing the shape of its evidence. The closest formal relative is AdoB (OOPSLA 2024), which relates benign and Byzantine consensus in Coq — with inverted polarity: it *unifies* the two fault models under one refinement abstraction, where this module makes their evidence deliberately type-incompatible. Both positions are coherent; a proof assistant wants one abstraction to prove things about, a programming interface wants substitution to fail loudly.

Engineering practice has been circling the same idea from below. In Sui's production Rust, a verified certificate is a distinct type that cannot be deserialized into existence, and the threshold *choice* is a const-generic parameter — `AuthorityQuorumSignInfo<const STRONG_THRESHOLD: bool>` selects between the `2f+1` and `f+1` bars — so weak-quorum evidence where strong-quorum evidence is required already fails to compile in a real blockchain. (One documented escape hatch exists, for trusted storage.) That is this module's move, minus the fault-model distinction: Sui's types live entirely inside one Byzantine protocol, and its certificates are signature sets, dissemination-style. On the theory side, behavioral types have been extending toward failure for a decade, and the frontier is instructive: multiparty session types now handle *crash-stop* failures, message loss, and unreliable links, with reliability assumptions carried in the types — and stop short of Byzantine. A fault model as a type parameter of evidence — crash versus Byzantine as unify-or-don't — is not something I found in the literature; stated with the same care as the previous post's version of this sentence, the search came back empty, which is a report about the search.

## What the gate cost

The whole module is seventy-five lines of executable code — the file is mostly documentation — took an afternoon including the literature check, and runs on stable Rust, which closes a loop worth naming. This rung sat parked for weeks behind a note that said the arithmetic needed type-level integers stable Rust doesn't have. That was true of the design as originally imagined, with `n` and `f` as const generics. It stopped being true the moment the [membership layer](disjoint-becomes-intersecting.md) settled its division of labor — types carry the epoch and the *relation*, runtime boundaries do all counting — and nobody went back to re-check the note. A parked blocker is indexed to the encoding that hit it. The design moved on; the blocker silently expired; the park note kept asserting it. The cheapest experiment this project ran was reading its own old assumption against its own current code.

---

🦬☀️ *quorum-types is a feasibility study — a distributed-systems generalization of warp-types. [GitHub](https://github.com/modelmiser/quorum-types).*
