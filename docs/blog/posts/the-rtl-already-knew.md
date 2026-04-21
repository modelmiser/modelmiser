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
given seed — trace J1 instructions from reset until the halt write,
counting retired instructions. Pure symbolic execution. For the
22-instruction countdown:

| Phase                            | Instructions |
|----------------------------------|--------------|
| Prologue (PC 0..1)               | 2            |
| Full loop iter (PC 2..9) × seed  | 8·seed       |
| Final iter (counter == 0)        | 6            |
| Exit path (PC 13..19)            | 7            |
| **Total**                        | **15 + 8·seed** |

`K_RTL` is the pipeline-startup constant — the difference between
instructions retired and cycles counted by the envelope. Derived
structurally from `super_j1_mailbox.v` + `latency_envelope.v`, it
encodes one cycle of IMEM read latency between `req_fire` asserting
and the first instruction becoming observable. So `K_RTL = 1`, and:

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
is not a countdown artifact. But countdown and echo are extremes —
maximal looping and zero looping. What if `K_RTL = 1` holds there
and breaks at intermediate loop sizes?

## Triangulating with coprime slopes

Design a third kernel that loops, but with a different per-iteration
count than the countdown. Specifically: *coprime* to the countdown's
8. Two measurements with proportional slopes don't rule out a hidden
constant that's a multiple of that slope. Two coprime slopes do.

The decrement kernel: 11 instructions with a 4-insn loop body
(`DUP; ZBRANCH exit; T-1; JUMP`). Per-iter count 4, coprime to the
countdown's 8.

| Phase                            | Instructions |
|----------------------------------|--------------|
| Prologue (PC 0..1)               | 2            |
| Full loop iter (PC 2..5) × seed  | 4·seed       |
| Final iter (counter == 0)        | 2            |
| Exit path (PC 6..10)             | 5            |
| **Total**                        | **9 + 4·seed** |

Extraction predicts `L(seed) = 10 + 4·seed`, envelope `Latency<10, 50>`.
Hardware validation is pending — the same IMEM-write path as the echo,
so the run is cheap. The prediction under `K_RTL = 1` is specific per
seed. If silicon agrees, `K_RTL` is independent of per-iteration
instruction count too. The pipeline constant is a property of the
pipe, not the program.

## What derivation buys you

Three kernels, one pipeline constant, predictive power across loop
topologies. What changes?

`Latency<L_MIN, L_MAX>` becomes a compile-time output, not a runtime
input. For kernels whose memory path is fully deterministic —
BRAM-resident, no SDRAM, no cache, no contention — the bounds are a
theorem about (RTL invariants) × (program CFG), not a measurement on
the hardware.

This complements runtime refinement rather than replacing it. Consider
the payoff-ratio frame:

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
despite half the absolute cycle reach. That tells you something: the
payoff spectrum is *shape-set* (by the `L_MIN/L_MAX` ratio), not
magnitude-set. Useful for deciding which kernels warrant the runtime-
refinement complexity. Look at the ratio, not the cycle counts.

## Where the extraction breaks

Every claim above assumes the memory path is deterministic. BRAM
reads are single-cycle. IO port accesses are single-cycle. No
contention, because there's only one master. Once SDRAM enters the
picture, the extraction formula needs a term for memory-access
variance, and the formula stops being an equation.

The planned SDRAM-touching kernel is where we expect extraction to
disagree with empirical measurement. That's the point where runtime
refinement becomes load-bearing: the static type declares
`Latency<16, 96>` as the *worst-case* envelope, and observation
refines it to an actual cycle count drawn from that interval.
Certifying extraction hands you the outer bounds for free; runtime
refinement tells you where in those bounds you actually landed.

Both techniques are complementary. The spectrum decides which one
does the work for a given kernel.

## What we actually showed

Two kernels cycle-exact against silicon, including seeds outside the
declared domain. A third with a coprime slope predicted but not yet
measured. A pipeline constant that survives changing loop topology.
`Latency<T, L_MIN, L_MAX>` goes from "type the runtime filled in after
observation" to "type the RTL filled in before the bitstream booted."

The envelope before the silicon. The RTL already knew.

---

🦬☀️ *Sol is a Lean 4 verification framework for deterministic
hardware. The extraction PoC — three kernels, three machine-checked
Lean theorem files, and a shared J1 symbolic-execution library — lives
in `active/sol/research/timed-session-types-runtime-refinement/extraction-poc/`.
warp-core is the J1 Forth mesh running on an ULX3S ECP5 FPGA.
[GitHub](https://github.com/modelmiser).*
