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

That argument quietly assumed something: we already knew the sender's
cycle was 3 and the receiver's cycle was 4. In the ping-pong example
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
For the 22-instruction countdown:

| Phase                            | Instructions |
|----------------------------------|--------------|
| Prologue                         | 2            |
| Full loop iter × seed            | 8·seed       |
| Final iter (counter == 0)        | 6            |
| Exit path                        | 7            |
| **Total**                        | **15 + 8·seed** |

`K_RTL` is the pipeline-startup constant — the difference between
instructions retired and cycles counted by the envelope. Derived
structurally from `super_j1_mailbox.v` + `latency_envelope.v`, it
encodes one cycle of IMEM read latency between `req_fire` asserting
and the first instruction becoming observable. The equation
`L = insns + K_RTL` is only that simple when the pipeline doesn't
stall mid-execution; for the J1's single-cycle ALU, branch, and
IO-port access instructions, it doesn't. So `K_RTL = 1`, and:

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

## A second kernel, nothing like the first

To test whether `K_RTL = 1` is a property of the pipeline rather than
the countdown, pick a second kernel that is as different from the
countdown as possible. No loop. No data dependence. Pure straight
line:

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
supports runtime IMEM updates. Five seeds, including 42 and 100
well outside the declared `[0, 10]` domain:

| seed | predicted | measured | delta |
|------|-----------|----------|-------|
|   0  |     8     |    8     |   0   |
|   1  |     8     |    8     |   0   |
|   5  |     8     |    8     |   0   |
|  42  |     8     |    8     |   0   |
| 100  |     8     |    8     |   0   |

Cycle-exact on every seed, including seeds we never declared. `K_RTL`
is not a countdown artifact.

## Triangulating with a different loop topology

Countdown and echo are the extremes — maximal looping and none at
all. What if `K_RTL = 1` holds at those poles but breaks for a loop
body of different size? A third kernel with a DIFFERENT per-iter
count than countdown's 8 tests whether K_RTL depends on loop shape
rather than loop presence.

The decrement kernel: 11 instructions with a 4-insn loop body
(`DUP; ZBRANCH exit; T-1; JUMP`). Half the countdown's per-iter
count, using only opcodes the J1 ISA already models — no new decoder
cases, no new `T_mux` selectors. The phase breakdown mirrors the
countdown's: prologue 2, full iter 4·seed, final iter 2, exit path 5.
Total `9 + 4·seed`, so extraction under `K_RTL = 1` predicts
`L(seed) = 10 + 4·seed`, envelope `Latency<10, 50>`.

This is a prediction, not a measurement. The decrement kernel hasn't
run on silicon — the prediction is just the extraction formula fed a
third program. Hardware validation is pending (same IMEM-write path
as the echo; no new bitstream). The point of the third kernel is to
stake out a *falsifiable* prediction: if silicon measures anything
other than `10 + 4·seed`, the "K_RTL is load-independent on this
pipeline" claim is wrong, and the nature of the delta tells us
whether the dependency is on per-iter count, program length, branch
density, or something else.

## What derivation buys you

Two kernels cycle-exact against silicon, a third whose prediction
stakes out the next measurement — what does that buy?

`Latency<L_MIN, L_MAX>` becomes a compile-time output, not a runtime
input. For kernels whose memory path is fully deterministic —
BRAM-resident, no SDRAM, no cache, no contention — the bounds are a
Lean 4 theorem about (RTL invariants) × (program CFG), not a
measurement on the hardware. The theorems live in
`TimedCountdown.lean`, `TimedEcho.lean`, and `TimedDecrement.lean`;
they typecheck on core Lean 4.28, no Mathlib, seconds to verify.

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
despite half the absolute cycle reach. Two data points on the
interval side is a thin sample, but the pattern is at least
consistent with a shape-set rather than magnitude-set payoff — the
`L_MIN/L_MAX` ratio predicts refinement's value, not the absolute
cycle count. A stronger version of this claim needs a fourth kernel
at a third magnitude.

## Where the extraction breaks

Every claim above assumes the memory path is deterministic. BRAM
reads are single-cycle. IO port accesses are single-cycle. No
contention, because there's only one master. Once SDRAM enters the
picture, the extraction formula needs a term for memory-access
variance, and the formula stops being an equation.

The planned SDRAM-touching kernel is where we expect extraction to
disagree with empirical measurement. A falsifiable prediction: the
delta scales with row-crossing count, not instruction count —
extraction predicts `L = insns + K_RTL`, hardware measures
`L + Σ row_crossings · K_row`, with `K_row` determined by the SDRAM
controller's auto-refresh and activation costs.

That's the point where extraction stops being an equation and starts
being a lower bound on a distribution. Runtime refinement earns its
keep: the static envelope declares the worst-case bound, observation
tells you where in that bound the specific run landed. Extraction
and refinement occupy different regimes, and the payoff ratio decides
which regime a kernel sits in.

## What survives the silicon

Two kernels cycle-exact against silicon, including seeds outside the
declared domain. A third with half the per-iter count predicted,
waiting for hardware to confirm or falsify. A pipeline-startup
constant that held across the two measured kernels and across the
ingress-to-halt boundary they share.
`Latency<T, L_MIN, L_MAX>` goes from "type the runtime filled in after
observation" to "type the RTL and the program filled in before the
bitstream booted."

The envelope before the silicon. For two kernels so far, the RTL
already knew.

---

🦬☀️ *Sol is a Lean 4 verification framework for deterministic
hardware. The extraction PoC — three kernels, three machine-checked
Lean theorem files, and a shared J1 symbolic-execution library — lives
in `active/sol/research/timed-session-types-runtime-refinement/extraction-poc/`.
warp-core is the J1 Forth mesh running on an ULX3S ECP5 FPGA.
[GitHub](https://github.com/modelmiser).*
