---
date: 2026-04-21
categories:
  - sol
  - warp-core
---

# The RTL Already Knew

Latency envelopes on deterministic hardware are derivable, not measurable.

<!-- more -->

## The envelope was assumed, not derived

[Intervals Collapse to Points](./intervals-collapse-to-points.md) argued
that timing proofs on deterministic hardware reduce to `rfl`. Core 0
sends at cycle 3, channel latency is 1, Core 1 receives at cycle 4:
`4 = 3 + 1`, done. No constraint solver, because every cycle count is
a compile-time constant.

That argument assumed something: we already knew the sender's cycle
was 3 and the receiver's cycle was 4. In the ping-pong example
those numbers were obvious — three instructions of compute plus a
channel latency. In general, a session type like
`Timed<T, L_MIN, L_MAX>` is a claim about an interval, and the
interval has to come from somewhere.

The traditional answer is runtime observation. Bocchi's Timed Multiparty
Session Types handle non-deterministic networks where you *can't* know
latency statically — the type system reasons over intervals because
the hardware genuinely varies. The bounds are inputs to the type
checker, not outputs.

On deterministic hardware, that's backwards. The bounds are latent in
the RTL and the program. You can extract them.

## The extraction formula

The J1 Forth core running in our mailbox harness: a request arrives
with a seed parameter, some J1 program computes, the result is written
to `io[0x20]`, and halt is signaled via a write to `io[0xFF]`. A
latency counter in the envelope module watches the request-to-halt
interval. That's `actual_cycles`.

The extraction claim is:

```
L(program, seed) = insns_executed(program, seed) + K_RTL
```

`insns_executed` is a function of the program's control flow for a
given seed — trace J1 instructions from `envelope_req_fire` until the
halt write, counting retired instructions. Pure symbolic execution.
For the 22-instruction countdown, the phases add up to `15 + 8·seed`:
two instructions of prologue, `8·seed` for the main loop, six for the
final iteration that exits the loop, and seven for the exit path that
writes the result and signals halt.

`K_RTL` is the pipeline-startup constant — the difference between
instructions retired and cycles counted by the envelope. Derived
structurally from `super_j1_mailbox.v` + `latency_envelope.v`, it
encodes one cycle of IMEM read latency between `req_fire` asserting
and the first instruction becoming observable. The equation
`L = insns + K_RTL` is only that simple under a handful of
assumptions: no pipeline stalls mid-execution (the J1's single-cycle
ALU, branch, and IO-port access instructions don't introduce any);
no interrupts or exceptions (the J1 mailbox doesn't implement any —
it's a request/response endpoint, not a preemptable core); no
contention from a second bus master (single-master assumption, no
DMA). Under those conditions, `K_RTL = 1`, and:

```
L(countdown, seed) = (15 + 8·seed) + 1 = 16 + 8·seed
```

For seeds in `[0, 10]`, the declared session-type domain, this gives
`Latency<16, 96>`.

## Silicon disagrees at its leisure

Extraction is a model. Hardware is a fact. Here's the delta between
prediction and the ULX3S running the countdown bitstream:

| seed | extracted | measured | delta |
|------|-----------|----------|-------|
|  0   |    16     |    16    |   0   |
|  1   |    24     |    24    |   0   |
|  3   |    40     |    40    |   0   |
|  5   |    56     |    56    |   0   |
| 10   |    96     |    96    |   0   |

Cycle-exact. Not ±1. Not "within measurement noise." The extraction
predicts silicon behavior exactly on every tested seed.

One kernel doesn't prove the methodology. It proves the methodology
*on this program*. The risk is that `K_RTL = 1` silently absorbs some
countdown-specific structural constant, and the match is a happy
coincidence. We need triangulation.

## A second kernel, along a different control-flow axis

To test whether `K_RTL = 1` survives the kernel choice, pick a second
kernel that differs from the countdown along the control-flow axis.
Same J1 core, same mailbox harness, same IMEM path, same halt
convention — everything from the ingress down is held constant. What
changes is whether the program has a loop at all.

The echo kernel: no loop, no data dependence, straight line.

```
PC 0: LIT 0x10          push read address
PC 1: io@T              T := io[0x10] = seed
PC 2: LIT 0x20          push result address
PC 3: T N->io[T] d-1    io[0x20] := seed
PC 4: LIT 0             halt-address setup
PC 5: LIT 0xFF
PC 6: T N->io[T] d-1    io[0xFF] := 0 → halt
```

Seven instructions. Extracted latency: `7 + K_RTL = 8`, constant
across every seed. The envelope collapses to a point:
`Latency<8, 8>`.

We loaded this via seven `xact(0, ...)` writes from a MicroPython
dispatcher — no new bitstream, because `super_j1_sptypes` already
supports runtime IMEM updates. Five seeds sweep cycle-exact to 8
across the board: 0, 1, 5, and two well outside the declared domain
(42 and 100). Delta zero on every run. `K_RTL` isn't absorbing a
countdown-specific structural term.

Worth naming what this test *doesn't* rule out. Echo and countdown
share the same ingress boundary (the `envelope_req_fire` pulse, the
1-cycle IMEM read) — any harness-level constant that both kernels see
by construction can't be distinguished from a true pipeline-wide
`K_RTL` by this pair. The cleaner framing: `K_RTL = 1` is derived
structurally from the RTL, and two cycle-exact silicon matches are
consistency evidence, not independent samples of a latent constant.

## A third kernel along the loop-body-size axis

Countdown and echo bracket the loop-presence axis (max iter vs zero
iter). They don't bracket the per-iter-count axis — the countdown's
body is always 8 instructions. A third kernel with a different
per-iter count pushes on that dimension. Whether silicon agrees or
disagrees then tells us something about *which* program feature
K_RTL might silently track: per-iter count, program length, branch
density, or something else. It's one more test point, not a separator
of those hypotheses individually.

The decrement kernel: 11 instructions, with a 4-insn loop body at
the core. Half the countdown's per-iter count, using only opcodes
the J1 ISA already models — no new decoder cases, no new `T_mux`
selectors.

```
PC 0: LIT 0x10           push read address
PC 1: io@T               T := io[0x10] = seed (initial counter)
PC 2: DUP                duplicate counter  ← loop top
PC 3: ZBRANCH PC=6       if counter == 0, branch to exit
PC 4: T-1                counter := counter - 1
PC 5: JUMP PC=2          loop back to PC 2
PC 6: LIT 0x20           exit path begins
PC 7: T N->io[T] d-1     io[0x20] := 0
PC 8: LIT 0
PC 9: LIT 0xFF
PC 10: T N->io[T] d-1    io[0xFF] := 0 → halt
```

Phase breakdown mirrors the countdown's: prologue 2 (PC 0-1), full
iter 4·seed (PC 2-5), final iter 2 (PC 2-3, with the ZBRANCH taken),
exit path 5 (PC 6-10). Total `9 + 4·seed` predicted under
`K_RTL = 1`, giving `L(seed) = 10 + 4·seed` and envelope
`Latency<10, 50>`.

This is a prediction, not a measurement. The decrement kernel hasn't
run on silicon — the prediction is just the extraction formula fed a
third program. Hardware validation is pending (same IMEM-write path
as the echo; no new bitstream). The point of the third kernel is to
stake out a *falsifiable* prediction: if silicon measures anything
other than `10 + 4·seed`, the "K_RTL is load-independent on this
pipeline" claim is wrong, and the nature of the delta tells us
whether the dependency is on per-iter count, program length, branch
density, or something else.

One caveat carries forward from the echo section: the decrement
shares the same ingress boundary as the other two. The third kernel
can't separate an ingress-level constant from a pipeline-wide
constant any better than the first two could. What it *will* stress
once silicon runs it is load-sensitivity across a non-trivial
program variation — a different question than ingress-vs-pipeline
composition, and one the earlier pair couldn't ask.

## What derivation buys you

Two kernels cycle-exact against silicon, a third whose prediction
stakes out the next measurement — what does that buy?

`Latency<L_MIN, L_MAX>` becomes a compile-time output, not a runtime
input. For kernels whose memory path is fully deterministic —
BRAM-resident, no SDRAM, no cache, no contention — the bounds are a
machine-checked Lean 4 theorem about (RTL invariants) × (program CFG),
not a measurement on the hardware.

This doesn't replace runtime refinement — the two techniques apply to
different regimes. Consider the payoff-ratio frame:

```
payoff_ratio(refinement) = (L_MAX - L_MIN) / L_MAX
```

That's the fraction of the worst-case cycle budget a runtime
observation can recover when the observed cycles come in below
`L_MAX`. For the three kernels:

| kernel     | envelope           | ratio |
|------------|--------------------|-------|
| countdown  | `Latency<16, 96>`  | 83%   |
| decrement  | `Latency<10, 50>`  | 80%   |
| echo       | `Latency<8, 8>`    |  0%   |

Runtime refinement earns its keep when the ratio is high. Countdown's
83% means knowing `actual_cycles = 16` (the fast-arm specialization)
recovers 83% of the reserved budget versus a worst-case policy.
Extraction earns its keep when the ratio is low: echo's 0% means
runtime observation adds nothing that `Latency<8, 8>` didn't already
declare.

Decrement at 80% is nearly indistinguishable from countdown's 83%
despite half the absolute cycle reach. Part of the "shape-set"
claim is trivially true by construction: the ratio
`(L_MAX - L_MIN) / L_MAX` is scale-invariant in magnitude whenever
shape is held constant — that's algebra, not data. What the two
data points *do* suggest, modulo a thin sample, is that real kernels
with similar `L_MIN/L_MAX` shapes produce similar payoff ratios
regardless of their absolute cycle counts. A stronger version of the
claim needs a fourth kernel with a different shape but a similar
magnitude to the decrement — that would separate "ratio holds when
shape is held" (algebraic) from "ratio holds across real programs"
(empirical).

## Where the extraction breaks

Every claim above assumes the memory path is deterministic. BRAM
reads are single-cycle. IO port accesses are single-cycle. No
contention, because there's only one master. Once SDRAM enters the
picture, the extraction formula needs a term for memory-access
variance, and the formula stops being an equation.

The planned SDRAM-touching kernel is where we expect extraction to
disagree with empirical measurement. Without running it, the shape
of the delta is speculation, but the plausible contributors are
separable by signature: per-row-activate costs would scale with
row-crossing count, bank conflicts would show pattern-dependence,
and refresh events would introduce bounded time-dependent jitter.
When the measurements come in, the task will be to decompose the
observed delta into those contributors — which is the work of
extending the extraction model, not just replacing it.

That's the point where extraction stops being an equation and starts
being a lower bound on a distribution. Runtime refinement earns its
keep: the static envelope declares the worst-case bound, observation
tells you where in that bound the specific run landed. Extraction
and refinement occupy different regimes, and the payoff ratio decides
which regime a kernel sits in.

## What survives the silicon

`Latency<T, L_MIN, L_MAX>` goes from "type the runtime filled in after
observation" to "type the RTL and the program filled in before the
bitstream booted." A consumer that takes a `Timed<T, L_MIN, L_MAX>`
sees the same contract either way; the only difference is *when* the
contract is available. Extraction offers it at compile time. What a
downstream pipeline does with that earlier availability — whether it
specializes on the bound, or just trusts it — is a separate
conversation.

The envelope before the silicon. For this harness, with these
kernels, the RTL already knew.

---

🦬☀️ *Sol is a Lean 4 verification framework for deterministic
hardware. The extraction PoC — three kernels, three machine-checked
Lean theorem files, and a shared J1 symbolic-execution library — lives
in `active/sol/research/timed-session-types-runtime-refinement/extraction-poc/`.
warp-core is the J1 Forth mesh running on an ULX3S ECP5 FPGA.
[GitHub](https://github.com/modelmiser).*
