---
date: 2026-08-02
categories:
  - crossdomain
---

# The Monitor Only Sees What Types Missed

We classified 1,500 runtime checks across four layers of one stack. Verification's reach is 88% at a protocol boundary and 2% at a dashboard — and it is the same software both times.

<!-- more -->

The question we set out to answer was whether unreliability is a *proof* gap. The type-theory work in this workspace keeps ending at the same wall: push an invariant as far as the type system will take it, and what refuses to go is always a fact that was true and became false — a stale cache line, a revoked lease, a superseded generation. Call it the residue. If that story is right, then real production reliability tooling should be overwhelmingly aimed at residue, and only marginally at things a compiler could have caught.

There was a cheap way to check. `mm-lux` is a Wayland and kernel invariant monitor we have been running against a live desktop for months. Its contracts accreted one incident at a time, with no taxonomy in mind — nobody chose those names to prove a point, which makes them evidence rather than illustration.

We classified all 107 contract identifiers in its sources by what kind of fact each one asserts. Three classes fell out.

**Thresholds on continuous quantities** — 64 of them, 60%. `system.psi.cpu_elevated` passes a literal `1.5` to its evaluator. There is no fact of the matter about "elevated" until somebody picks that number, and the number is a policy decision wearing the costume of an observation.

**Revocable facts** — about 20. `wayland.app.output.stale_response`, `wayland.surface.leave_orphan` (a leave for an output the surface *never entered*), `vm.cgroup.oom_kill`. Was true, became false.

**Typestate across a process boundary** — 4. `wayland.surface.commit_without_attach`, `xdg_surface.configure_ack`, `wayland.server_new_id.range`. These are perfectly typeable *in-process*; a Rust typestate encoding makes `commit` before `attach` fail to compile. They escaped to runtime only because the compositor does not own the client's compiler.

Four out of 107. That is a striking number, and it is the number we nearly published.

## The second corpus agreed, which is what made it dangerous

One corpus proves nothing, so we ran a second: [awesome-prometheus-alerts](https://github.com/samber/awesome-prometheus-alerts), 1,155 curated alert rules spanning cluster and service operations. Different domain, different authors, different decade, different assertion language — and every rule carries its PromQL expression, so we could classify on the *shape of the predicate* rather than the wording. Equality or absence (`up == 0`, `absent(job)`, `changes()`) means a fact that flipped. An inequality against a literal (`> 0.9`, `< 10`) means a line somebody drew.

The results: 78.6% threshold, 21.4% revocable, 0.6% unclassified, and zero typestate. Against mm-lux's 76.2 / 23.8. Two independent corpora agreeing within 2.4 points.

It is a seductive result. It says the reliability effort is aimed at the wrong few percent — that "verify more" targets 0–4% of what actually breaks, and the other 96% splits between facts that changed and numbers somebody chose, neither of which is a proof problem.

We had already written that conclusion down when we noticed what both corpora had in common. They are both **monitors**.

## The protocol layer says the opposite

Wayland is unusual: its obligations are *declared*. The core protocol and 36 extensions ship machine-readable `<enum name="error">` blocks — 172 named error conditions across 77 interfaces, each one a thing a client can do wrong, written by the people who designed the boundary. That is an assertion set nobody assembled to make a point, same as mm-lux, but sampled from a completely different altitude of the same stack.

It immediately broke the taxonomy. `wl_surface.invalid_transform` says the transform argument must be one of eight enum values. That is not a threshold — no number, no cutoff. It is not typestate either — no history, no ordering. It is a monotone predicate on a single value, and it is the *cheapest* thing in the entire taxonomy to eliminate: a real enum in the generated binding makes the illegal value unrepresentable, no session types required. Metrics corpora contain none of these, because a monitor never validates an argument; by the time a number reaches a time series it has already been accepted.

So the scheme grew a fourth class — **domain** — declared before we looked at any counts, because folding it into typestate would have been exactly the error the method is supposed to prevent.

With four classes, across 172 declared errors:

| Class | Count | Share |
|---|---|---|
| Typestate | 82 | 47.7% |
| Domain | 67 | 39.0% |
| Threshold | 8 | 4.7% |
| Revocable | 6 | 3.5% |
| Server-side / ambiguous / unclassified | 9 | 5.1% |

Eliminable by a type — domain plus typestate — is **87.6%** of the client-facing errors.

Then the implementation, to make sure this was not an artifact of specs being aspirational. [Smithay](https://github.com/Smithay/smithay) is the Rust compositor library that `cosmic-comp` is built on. It emits 66 distinct protocol errors across its `post_error` call sites. Classified the same way: 47.0% typestate, 36.4% domain, 9.1% threshold, 1.5% revocable. **83.3% eliminable.**

## Four altitudes of one stack

| Layer | Corpus | n | Domain | Typestate | Revocable | Threshold |
|---|---|---|---|---|---|---|
| protocol spec | wayland-protocols | 172 | 39.0% | 47.7% | 3.5% | 4.7% |
| protocol impl | smithay `post_error` | 66 | 36.4% | 47.0% | 1.5% | 9.1% |
| runtime monitor | mm-lux | 107 | — | ~4% | ~24% | ~76% |
| ops monitor | prometheus alerts | 1155 | — | 0% | 21.4% | 78.6% |

These four corpora do not disagree. `mm-lux` *monitors Wayland*. `cosmic-comp` is built on smithay. This is one stack measured at four heights, and the mix inverts almost perfectly as you climb.

The mechanism is simple once you say it out loud: **the eliminable classes are consumed where they are caught.** A protocol error kills the client at the boundary. It never becomes a metric, never reaches a dashboard, never appears in an alert rule. Everything that survives to the monitoring layer has already been filtered of the things a type could have caught — which is precisely *why* a monitor sees only revocable facts and thresholds. Both measurements are correct. Neither generalizes to "software."

The clearest evidence is a single obligation visible at two altitudes. Wayland declares `xdg_surface.not_constructed` — a surface committed before it was fully constructed. `mm-lux` independently implements `wayland.surface.commit_without_attach`, which watches the wire for the same violation from outside. One obligation, declared at the boundary and re-checked at the monitor. It is 1 of 82 typestate errors at the protocol layer and 1 of 4 at the monitoring layer, and the difference between those denominators is the whole finding.

## The question that actually has an answer

"What fraction of failures can verification catch?" turns out to be unanswerable. It is 88% or 2% depending on where you stand, and every published number of that shape is really a statement about the author's vantage point — including the one we nearly published.

The answerable question is different:

> Does this boundary have a declared obligation set at all?

Wayland has 172, specified, versioned, machine-readable, with a reference implementation enforcing them. That is extraordinary and almost nobody does it. The median internal API — the module seam, the plugin ABI, the service call, the FFI shim — has zero. Not "few." Zero, because nobody ever wrote them down.

Where obligations are never declared they are never checked, and they do not disappear. They resurface downstream as behaviour nobody can explain: the intermittent failure, the thing that only happens under load, the bug that closes as "could not reproduce." That reads as irreducible complexity. Some of it is — the residue is real, and revocable facts genuinely need a clock that no type can provide. But a large fraction of what gets *filed* as irreducible is an undeclared spec, and the two are indistinguishable from the monitoring layer, because the monitoring layer is exactly where the distinction has already been erased.

Two smaller findings worth carrying:

**Domain errors are nearly free and nobody collects them.** 36–39% of Wayland's declared errors are single-argument validation. No ordering machinery, no session types — a generated binding with real enums and newtypes removes them outright. That is the cheapest reliability work available at any boundary, and it is sitting uncollected at the one boundary that bothered to write its obligations down.

**Implementations under-enforce uniformly, not selectively.** Smithay emits 62 of the 172 declared errors — 36% spec coverage — while matching the spec's class mix almost exactly (36.4 / 47.0 against 39.0 / 47.7). It is not skipping hard checks and keeping easy ones. It is simply thinner everywhere. Coverage is a volume problem, not a prioritization one, which is good news: it is the kind of gap that closes with generation rather than judgment.

## What we are not claiming, and one bug worth your time

Four corpora is four corpora. Two of them are Wayland, so the protocol-layer numbers rest on a single protocol family — a boundary designed by people unusually committed to specifying it, which is close to a best case. The monitoring-layer corpora are broader, but the `mm-lux` row is the softest in the table on two counts: its classification was name-based rather than predicate-based and left 18% unclassified, and its population is a superset of the live registry — we extracted 107 contract identifiers from the contract sources, where the project's own documentation counts 87 registered. Ratios are what the argument rests on, not the denominator, but treat that ~4% typestate as the weakest number here. Nothing above says the layer effect holds at a ratio anyone should quote. It says the effect exists and is large.

One methodological note, because it nearly cost us the result. Our first pass over the Wayland corpus put 50 of 172 errors — 29% — into the unclassified bucket. Reading them turned up the cause: `\b` in a regular expression treats `_` as a *word character*, so `\balready\b` never matches `already_captured` and `\bunsupported\b` never matches `unsupported_buffer`. Every snake_case identifier in a corpus made entirely of snake_case identifiers had been silently failing to match. Normalizing `_` to a space before matching took unclassified from 29.1% to 1.2% and moved typestate from 33% to 48%.

A classifier that could not say *I don't know* would have reported that 33% cleanly and confidently. The mandatory unclassified bucket is not hygiene; it is the only thing in the method that can fail loudly, and it caught every defect we found — including, on the very first pass over `mm-lux`, fourteen D-Bus and varlink interface names plus twenty-one unrelated `verify.*` facts that an over-greedy regex had swept in as if they were contracts.

We also left five errors classified as genuinely ambiguous rather than picking. All five say some variant of *"the associated wl_surface was destroyed."* If the client destroyed it, that is a linearity break — use-after-destroy, textbook typestate. If the compositor did, the child object's validity was revoked underneath the client — residue. The protocol text does not say which, and neither do we.

---

🦬☀️ *Classifier, taxonomy, and calibration data ship as `mm-residue`. Corpora: [awesome-prometheus-alerts](https://github.com/samber/awesome-prometheus-alerts), [wayland-protocols](https://gitlab.freedesktop.org/wayland/wayland-protocols), [smithay](https://github.com/Smithay/smithay).*
