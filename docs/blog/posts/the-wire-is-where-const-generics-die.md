---
date: 2026-07-13 06:00:00
categories:
  - quorum-types
---

# The Wire Is Where Const Generics Die

Every quorum certificate in this crate is indexed by a compile-time epoch; a socket hands you the epoch as eight bytes. What survives that crossing is worth stating exactly.

<!-- more -->

## A blocker, taken at its word

This is the seventh post on quorum-types, a feasibility study asking whether the compile-time safety of [warp-types](what-the-type-erases-to.md) — typestates for GPU warps — survives the move to a distributed system; the series climbs one ladder, a rung per result. Since the [first post](split-brain-unrepresentable.md), the crate has carried a parked note: network simulation deferred, because a network simulator wants an async wire protocol and the toy has none. The crate's simulation of crash, partition, and heal ran [in-process](split-brain-unrepresentable.md) instead — roles as function calls, one shared clock, the partition a boolean.

Unparking the note meant building the wire protocol. Building it did not remove the obstacle — it located it: the protocol's absence had been marking the exact position of a limit in the type discipline, and the note had been pointing at that limit the whole time.

The limit is easy to state. The crate's certificate types — `Quorum<E>`, `LeasedQuorum<E>`, `ByzQuorum<E>`, the `Leased<E>` authority token — are indexed by `const E: u64`, a compile-time epoch. That is the design's whole trick: certificates from different configuration generations refuse to unify, so cross-epoch merges fail to typecheck. But a const generic must be a compile-time constant — the Rust Reference is unambiguous — and no mechanism, stable or otherwise, lifts a runtime integer into one. An epoch that arrives as eight bytes off a socket is runtime data. You cannot enumerate every possible epoch as a `match` arm, one monomorphization each — the specialized copy of the code the compiler stamps out per const value — because there are 2^64 of them.

So the question this rung pre-registered: when the epoch must cross a wire, does the type discipline survive on the far side? Four ways this could have died were written down before the test harness existed; two are structural and frame this post (the other two — a negative control that refuses to fail, and broken determinism — reappear below as tests). First structural falsifier: the discipline collapses into runtime `u64` comparisons throughout, certificates constructed ad hoc instead of minted at the `certify` boundary (the check-once-then-spend-structurally pattern the crate is built on) — in which case network-testing this crate is ordinary property testing and the rung adds nothing new. Second: the simulator forces async machinery into the dependency-free library, costing more than it measures.

## A network you can replay

The instrument is [turmoil](https://github.com/tokio-rs/turmoil), the tokio project's deterministic network simulator. It runs every host as a future on a single thread, virtualizes time, simulates UDP and TCP between hosts addressed by name, and seeds all of its own randomness; the network's failure modes are ordinary function calls — `partition("leader", "candidate")` is a line of test code, not a firewall rule. This is the testing lineage FoundationDB made famous and TigerBeetle's fault-injecting cluster simulator carries on: the whole cluster inside one deterministic process. Turmoil is the small Rust member of the family.

The obvious alternative instrument is strictly more powerful and still wrong. Stateright, a Rust model checker, has you describe the system as actors and exhaustively enumerates their interleavings; but the exhaustive work is already done. Back in the [first post](split-brain-unrepresentable.md), TLC, the TLA+ model checker, produced the counterexample this crate has been replaying ever since: drop the lease guard — the rule that a new configuration must wait out the old leader's time-bounded lease — and split-brain appears at depth four. This rung needs that known trace *replayed as network events*, under a handful of seeds — a scripted schedule engine, not a second search that pays for the proof twice.

Determinism, it turns out, is a buy-in rather than a gift. Turmoil runs hosts on one thread, but the harness has to cooperate: ordered collections only (a `HashMap`'s iteration order would inject its randomly seeded hasher into the schedule), no `tokio::select!` (its branch choice is random by default), no threads, no wall clock — ticks come from virtualized elapsed time. No compiler checks any of that, so one test runs the same seed twice and asserts the two event traces are identical, byte for byte. It passes — seed sweeps produce *reproducible* counterexamples, the property that justifies this style of testing at all.

## The bridge that isn't there

Is there any principled way to make a runtime-parsed epoch type-level again?

Rust practice comes tantalizingly close with *branding*: GhostCell (ICFP 2021) and the branded-index technique before it mint an invariant lifetime — a fresh, anonymous type-level name — inside a scope and tie runtime values to it; two brands can never be confused, because the compiler refuses to unify them. That sounds like exactly the tool: parse an epoch, mint a brand for it, and certificates from different parse events become type-incompatible.

It is the wrong shape, for a reason worth keeping. A brand is anonymous and scope-tied — it carries no epoch *value* at the type level, only distinctness — and Rust has no way to go back: no analogue of Haskell's `TestEquality`, no runtime comparison that yields a type-level *equality witness* for two brands that happen to name the same epoch, because an invariant lifetime is invisible to `TypeId`, the one runtime type-test Rust has. (For ordinary `'static` types, `Any::downcast` can mint such a witness — but only between types you can already write down: monomorphizations again.) Quorum work needs that step constantly — an epoch-indexed certificate exists to *aggregate* same-epoch evidence and *refuse* the rest. Branding can make two parsed epochs distinct; it can never make them provably equal again — and a discipline that could only sunder would refuse the valid case along with the invalid one.

What remains is folklore so common it has no canonical name. A runtime value cannot become a const generic, but it can *select among* monomorphizations that already exist — condensed here from the harness's dispatch loop, with `heard_epoch` being wire data that has already passed the checked boundary described in the next section:

```rust
// The workaround: data selects among compiled epoch spaces.
match heard_epoch + 1 {
    1 => elect_and_serve::<1>(&sock, &reg, prior_lease).await?,
    2 => elect_and_serve::<2>(&sock, &reg, prior_lease).await?,
    other => refuse(other), // no compiled epoch space for `other`
}
```

Inside an arm, everything is typed again: the epoch-1 leader loop is monomorphic in its epoch, the quorum it certifies is `E = 1`-indexed, and handing its certificate to epoch-0 code is still a compile error. The first falsifier is half dead — the discipline did not collapse into runtime comparisons; whether certificates still get *minted* at the `certify` boundary when the votes come off a wire is the scenario's job, below. What the `match` establishes is the shape of the survival: the discipline holds per monomorphization, the runtime epoch's one power is selection, and the arms are, literally, the epochs this binary is compiled to speak; data outside them gets refusal, the correct answer to an epoch you have no code for.

## One function wears all the trust

The harness's protocol is deliberately primitive: 25-byte UDP datagrams — a tag byte and three little-endian `u64` words — carrying heartbeats, vote requests, and votes among three hosts. No serde, no schema, nothing to hide the interesting part, which is a single function:

```rust
/// The promotion boundary: the sole crossing from wire bytes to typed values.
fn promote(datagram: &[u8]) -> Option<Msg>
```

Every wire-derived value any host feeds into the typed API — every parsed `NodeId`, epoch, lease — passes through `promote`: the one place bytes become values, and where the arithmetic gets checked. A frame's numbers are operands-in-waiting: the lease constructor computes `granted_at + ttl` and the candidate computes `epoch + 1` — each a single hostile frame away from a panic in debug builds and a silent wrap in release, since two `u64::MAX` words make an overflowing lease and an all-ones epoch has no successor. A node identifier, meanwhile, must fit the crate's 32-bit `NodeId` — the tempting `as u32` truncation would silently alias another member, so the boundary converts checked. `promote` performs all three checks and answers `None` before any consumer touches the operands.

The [previous post](the-famous-number-assumes-a-signature.md) watched an "infallible" witness panic in safe code the moment an operator promise broke, and the wire is where such assumptions break routinely. This boundary's first draft proved it by missing one check: it verified the lease addition but let the epoch through raw, and a test that built a heartbeat carrying `u64::MAX` watched it sail through `promote` and panic the candidate's dispatch. The successor check exists because the exploit came first; the boundary learned to refuse it afterward.

What `promote` cannot do is verify that the bytes told the truth. A peer that announces a shorter lease than it actually holds will induce a perfectly type-correct early failover; a peer that announces a longer one can stall failover with a single lie — report an expiry far enough out and the candidate waits forever. The typed API verifies all the counting downstream of promotion — subset checks, thresholds, lease comparisons — and nothing verifies honesty at it. This is the series' recurring law again — types verify chains; operators choose roots. The [membership constructor](up-is-gated-down-is-free.md) was the first root, [caller-chosen samples](a-merge-is-a-proposal.md) the second, the [declared fault budget](the-famous-number-assumes-a-signature.md) the third. The deserializer is the fourth, and it is the outermost: every other root is chosen by an operator standing inside the process; this one admits the world.

The nearest literature frame, Gradual Session Types (Igarashi, Thiemann, Vasconcelos, and Wadler, 2017) — static protocol types meeting dynamic code across runtime-checked casts — assigns blame when a cast *fails*. The interesting case at `promote` is a cast that *passed* on lying bytes, and that is exactly where the boundary hands off to the trust model: the root answers for it, not the chain.

## The same counterexample, now with a real partition

The scenario gives the TLA+ counterexample's partition its third incarnation, each one more real. In the model it was a state transition. [In-process](split-brain-unrepresentable.md) it was a boolean the harness respected. Here it is `turmoil::partition`, and messages actually stop arriving.

Three hosts: a leader serving epoch 0 under a lease valid through t=5, heartbeating its lease terms; a candidate watching for silence; a voter. The driver isolates the leader at t=2. The candidate hears nothing for three ticks, solicits votes over the wire, and certifies a real quorum from its own vote plus the voter's parsed response — the crate's own `certify`, its remote input fed through `promote`, and the first falsifier's other half dead with it. Then it attempts failover, and the guard the TLA+ model proved necessary fires on schedule:

```text
t=0  leader serving e0
t=2  driver: leader isolated
t=4  candidate: leader silent, seeking e1
t=4  voter grants e1
t=4  quorum certified at e1: {2, 3}
t=4  reconfigure refused: prior lease valid until t=5
t=6  leader stopped serving
t=7  reconfigure permitted: prior lease lapsed
t=7  candidate serving e1
t=12 driver: partitions healed
t=12 leader learned e1 is serving
```

No overlap: "valid until t=5" is inclusive, so t=5 is still the old leader's; its first tick out of service is t=6, and the candidate — waiting two ticks past the *reported* expiry — serves at t=7. That leaves t=6 as the tick nobody serves, the visible gap, and the two-tick slack behind it is the harness's stand-in for bounded clock skew. (The in-process sim had one `now` and never thought about skew; per-host clocks make the assumption visible, so it is named as an axiom rather than modeled.) The test asserts the no-split-brain invariant at every serving-set change, across several seeds (which, at this harness's one-second tick granularity, reproduce the identical trace — reproducibility, not schedule variety), and — the part that keeps a green run honest — asserts the *refusal happened*: a run in which the guard never fired would test nothing, and that vacuity is the failure mode this series keeps hunting (most recently in the [fifth](a-merge-is-a-proposal.md) and [sixth](the-famous-number-assumes-a-signature.md) posts).

Then the negative control. Same schedule, same election, same certified quorum — one change: instead of asking `reconfigure` for permission, this run's unguarded twin mints its authority directly through `genesis`. The trace where it diverges from the guarded run, with the violation record appended:

```text
t=4  UNGUARDED: minting authority via genesis, ignoring the prior lease
t=4  candidate serving e1        ← leader is still serving e0
t=4  split-brain: [candidate=e1, leader=e0]
```

Two leaders at t=4 — the exact transition the unguarded TLA+ model produced at depth four, now manufactured by an actual network partition and a bypassed check. And the twin never leaves the library to do it: `genesis` is a legitimate API — the operator-root constructor by which any epoch's configuration, epoch 0 included, comes to exist — and used away from genesis, it is the bypass. The negative control is not an attacker breaking the types; it is an operator breaking the promise the types were always explicit about not checking. The escape hatch and the root of trust are the same door.

The pre-registration missed one thing. After the guarded leader's lease lapses, it surrenders its token — and `surrender` takes the token by value. The deposed leader cannot re-serve epoch 0 *with the authority it had*: that value no longer exists in its process, so the classic stale-holder-revival bug has no state to revive from — not a cleared flag, an absence. Rust's move semantics did temporal work. (Fresh epoch-0 authority is still mintable — via `genesis`, or via `reconfigure::<0>`, since nothing enforces that a new epoch exceeds the old; either is an operator promise broken on purpose, not a stale flag flipping back on.) The in-process sim called `surrender` too — but there the stale-holder check ran against a lease value the harness had kept a copy of, so the moved-away token carried no weight. The token itself only becomes the mechanism when a long-lived process survives its own deposition; only such processes give affine types — values the compiler lets you use at most once — something to be affine *about*.

## Fencing the claims

Typed protocols exist in Rust, and the fence between them and this rung is instructive. Ferrite (ECOOP 2022) and Rumpsteak (PPoPP 2022) both embed session types — protocol state machines checked at compile time — and both transport *native Rust values* between participants compiled into one typed program. Adversarial bytes never arrive; the question this rung is about cannot arise in their model, because the wire is inside the trust boundary. NEST (ECOOP 2026) attacks the same gap from the opposite side, moving protocol enforcement into the network fabric itself with programmable-switch monitors, on the premise that endpoint enforcement cannot be trusted past the wire. This toy's answer is the small one: keep the endpoint types, and give the boundary a name and a single function.

On the simulation side, this rung's direction — spec to implementation — is an occupied lineage: Mocket (EuroSys 2023) and SandTable (EuroSys 2024) replay model-checker traces against real implementations — Mocket by instrumenting them, SandTable by interposing on unmodified ones — and the Confidential Consortium Framework's verifiers (NSDI 2025) translated TLC counterexamples into deterministic functional tests run through a fault-injecting scenario driver — spec counterexample to executable replay, the whole direction. The last two posts each closed their related work by claiming one small unoccupied square; this one closes differently. Replaying your model checker's counterexample against your implementation is established practice this toy *joined*; the only piece without precedent I could find — an off-the-shelf socket-level network simulator as the replay harness — is a convenience, not a contribution. What the rung can call its own is the measurement: the discipline is per-monomorphization, and the wire carries only selection. The simulation methodology is borrowed with gratitude.

And the fences on the artifact itself: one scripted candidate (no competing elections); no lease renewal (the epoch-0 leader serves one lease and yields); unauthenticated datagrams, because this is the *crash* rung over a wire — Byzantine values stay behind [the previous rung's fence](the-famous-number-assumes-a-signature.md); and the split-brain observer is trusted test scaffolding outside the network, as it was in-process. The types constrain each node's local transitions. The simulation tests whether the message protocol *driving* those transitions composes under adversarial delivery. Those are different claims, and conflating them is the overclaim this post exists to avoid.

## What the gate cost

A 445-line test file, an afternoon including the literature check, and two dependencies that are dev-only: the library's own dependency section is still empty, so the second falsifier — async contamination of the dependency-free core — never happened either.

The [previous post](the-famous-number-assumes-a-signature.md) closed on a parked blocker that had silently expired — a note indexed to an abandoned encoding, asserting a limit the design had walked away from. This rung's park note is the complementary case: it had not expired at all. The note — "needs a wire protocol first" — was true, stayed true, and turned out to be the finding wearing a to-do's clothing; building the protocol first located the obstacle, then measured it. Between them the two notes make the general point: a parked blocker is a claim about an encoding, and the only way to learn whether it has expired or matured is to take it at its word — reread it against the code, or build against it.

Down the series' ladder, the evidence reads: a counted majority, a sampled law, a counted supermajority conditional on a declared budget — and now the counted majority again, unchanged, its provenance demoted: the votes that complete it arrived as bytes an adversarial network delivered. The guarantee was never "split-brain is impossible in the world." It was always "split-brain is unrepresentable in any process that keeps its promises at the roots" — four of them now, ending at the bytes. Six rungs before this one bought the chain. The wire is where you learn what it was anchored to.

---

🦬☀️ *quorum-types is a feasibility study — a distributed-systems generalization of warp-types. [GitHub](https://github.com/modelmiser/quorum-types).*
