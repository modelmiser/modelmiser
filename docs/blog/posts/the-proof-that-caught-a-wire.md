---
date: 2026-04-14 16:00:00
categories:
  - Sol
---

# The Proof That Caught a Wire

When native_decide returns false, the bug is real.

<!-- more -->

## The wrong channel

J12's program said `recv_right`. J11 is to J12's left.

On real hardware — a J1 Forth mesh processor, nine deterministic cores connected by CSP channels — this would have been a silent deadlock. Data sitting in `chan_right_fwd` while J12 polls an empty channel forever, one core waiting for data that will never arrive because it's looking in the wrong direction.

The code read naturally. J12 receives the result. But "the result" comes from J11, and J11 is *leftward*. The correct instruction is `recv_left`. The same directional error appeared in J10's program: `recv_left` when J11 is to J10's right. Both bugs look correct if you think about *what* the core is doing. They're wrong when you think about *where* the data is.

At three cores with four channels, I missed it reading the code. At nine cores with twelve channels, I wouldn't have a chance. The proof checker caught it in 294 milliseconds.

## Timed session types

The context is Sol's timed session type library — 36 machine-checked theorems across three Lean 4 files, built on `Sol.Lib.Invariant`'s `iterate_invariant` combinator. Session types describe communication protocols at the type level: who sends what to whom, and in what order. Standard session types for networks specify what data flows. Timed session types add *when*.

For the J1 mesh, "when" means exact cycle numbers. Each J1 instruction takes exactly one cycle. Channel latency is exactly one cycle. The system step function — `ThreeCoreSystem.step` — is a pure function from state to state. No scheduling nondeterminism. No cache variability. No branch prediction. One input produces one output, always.

The type annotations read like a timing diagram compressed into a type signature:

```text
Forward channel (J10 → J11):
  J10 (sender):   !u16 @3 . end @10
  J11 (receiver): ?u16 @4 . end @8

Reverse channel (J11 → J10):
  J11 (sender):   !u16 @7 . end @8
  J10 (receiver): ?u16 @8 . end @10
```

`!u16 @3` means "send a u16 at cycle 3." `?u16 @4` means "receive a u16 at cycle 4." The timing consistency proof — send at cycle 3 plus latency 1 equals receive at cycle 4 — is `rfl`. Literally reflexivity. The two sides of the equation reduce to the same natural number, and Lean confirms it without any proof search at all.

## The two-core trace

Before the three-core spine where the bug appeared, the simpler case establishes the method. Two cores, ping-pong: Core 0 computes a value and sends it to Core 1, Core 1 processes it and sends the result back.

```text
Core 0:                            Core 1:
  cycle 0: compute (LIT 42)         cycle 0: recv_fwd (blocks)
  cycle 1: compute (LIT 7)          cycle 1: (blocked)
  cycle 2: compute (ADD)             cycle 2: (blocked)
  cycle 3: send_fwd ──────────►     cycle 3: (blocked)
  cycle 4: recv_rev (blocks)         cycle 4: recv_fwd completes
  cycle 5: (blocked)                 cycle 5: compute (LIT 2)
  cycle 6: (blocked)                 cycle 6: compute (MUL)
  cycle 7: (blocked)                 cycle 7: send_rev
  cycle 8: recv_rev completes  ◄──  cycle 8: halt
  cycle 9: compute (output)
  cycle 10: halt
```

Core 0: 3 compute + send + block + recv + output = 10 cycles. Core 1: block + recv + 2 compute + send = 9 cycles. The blocking durations are the interesting part. Core 1 blocks from cycle 0 to cycle 4 — four cycles, waiting for Core 0 to finish computing and for the data to traverse the channel. Core 0 blocks from cycle 4 to cycle 8 — four cycles, waiting for Core 1 to process and for the return trip.

The termination proof is `native_decide`. Lean evaluates `TwoCoreSystem.step` twelve times starting from `TwoCoreSystem.initial`, checks that both cores are halted, and returns `true`. No induction. No case analysis. Just evaluation. The theorem `system_terminates_at_10` compiles — which means it's true — in 294 milliseconds.

Deadlock freedom is the same technique applied at every step:

```lean
theorem deadlock_free_all_steps :
    TwoCoreSystem.all_safe pingPongProgram 12 = true := by native_decide
```

`all_safe` checks every intermediate state from cycle 0 to cycle 12: at each step, either both cores have halted, or at least one core is not blocked, or a blocked core has data in flight on its incoming channel. Twelve states, twelve checks, one call to `native_decide`.

## The three-core bug

The spine topology adds a routing core. J10 sends data to J11, J11 forwards it to J12, J12 processes it and sends the result back through J11 to J10. Three cores, four channels. J11 is the router — it receives from both directions and forwards in both directions.

I wrote the programs the way they sounded in my head. J10 sends its value rightward and waits for the result. J11 receives from the left, forwards to the right, receives the processed result from the right, sends it back to the left. J12 receives the data, processes it, sends it back.

The spine termination theorem:

```lean
theorem spine_terminates :
    (runSpine 20).terminated := by
  unfold ThreeCoreSystem.terminated; native_decide
```

`native_decide` returned `false`.

Lean simulated 20 steps of the three-core state machine and found that the system never terminates. Not "might not terminate under some scheduling" — *does not terminate* under the only scheduling that exists. Deterministic hardware, deterministic simulation, definitive answer.

The diagnostic was immediate once I looked at the topology instead of the English description. J12's program started with `recv_right`. But J11 sends data to J12 via `chan_right_fwd` — the channel whose data arrives on J12's *left* input. J12 was polling its right channel, which connects to nothing. Data was sitting in `chan_right_fwd`, ready to be consumed, while J12 waited forever on an empty channel.

The same mirror-image error hit J10. The result coming back from J11 arrives on J10's *right* input (via `chan_left_rev`), but J10 was polling `recv_left`.

Two `recv_right` → `recv_left` substitutions, one `recv_left` → `recv_right` substitution. Run `native_decide` again. `true`. All 20 steps deadlock-free. All three cores halt.

## Why this works

`native_decide` works here because the hardware is deterministic. The step function `ThreeCoreSystem.step` takes a `ThreeCoreSystem` and a `SpineProgram` and returns a `ThreeCoreSystem`. No randomness. No scheduling choice. No IO. Lean's kernel can evaluate it as a pure computation and compare the result to `true`.

The standard reference for timed session types — Bocchi, Yang, and Yoshida's work from CONCUR 2014 — uses clock *intervals* because their target is non-deterministic networks where latency varies. On deterministic hardware, those intervals [collapse to points](intervals-collapse-to-points.md). The timing consistency proofs become `rfl` — reflexivity, the simplest proof in Lean's kernel. The full Sol build (1486 jobs, 0 failures) includes the timed session proofs without an SMT solver or model checker. They need `rfl` and `native_decide`. The proof technology is mundane. The leverage comes from the hardware.

## Scaling

The D4 symmetry module (`TimedSessionD4.lean`) already demonstrates the scaling argument for the full 3x3 mesh. The four corner bridges — where warp units attach to corner J1 cores — are related by 90-degree rotation. Any property proved for one corner holds at all four:

```lean
theorem bridge_session_position_independent (p w : Nat) (c1 c2 : Corner) :
    bridge_protocol p w (bridge_channel c1).latency =
    bridge_protocol p w (bridge_channel c2).latency := by
  simp [bridge_channel]
```

One proof, four corners. The session type depends on the protocol parameters and the uniform channel latency, not on which corner of the grid you're at. Twelve theorems in the D4 module, all machine-checked, turning what would be 4N proofs into N+3.

Each channel in the mesh gets its own timing proof, verified independently. The coupling between channels happens only at shared cores, where one channel's session type determines when the core is available to service another channel. For a 3x3 mesh with 12 channels, that's 12 independent timing proofs plus coupling constraints at the 5 shared cores — not 72 pairwise proofs.

## The directional error in context

The original bug was a mistake about spatial relationships, not about protocol logic. The communication *protocol* was correct: J12 receives data, processes it, sends a result. The *direction* was wrong: J12 looked right when the data was coming from the left.

This is the class of bug that gets harder exactly as fast as the system scales. At 3 cores, you can trace the topology in your head, and I still got it wrong. At 9 cores with 12 channels and 4 warp bridges, the directional relationships form a graph that exceeds casual spatial reasoning. At 16 cores in a 4x4 mesh with 24 channels, it's hopeless without mechanical checking.

And on real hardware — the ULX3S board running a J1 mesh at 33 MHz — this bug class is a silent deadlock. No assertion fires. No exception throws. One core just stops. The others might keep running, serving stale data, or they might block in turn, waiting for a result that's stuck behind the first deadlock. The failure mode is absence: the system does less than it should, and the only symptom is that expected output never arrives.

`native_decide` turned a 20-step simulation into a proof obligation, and the proof checker said no. That "no" was worth more than any number of test runs, because it was exhaustive over the only execution that exists. On deterministic hardware, simulation *is* proof. And when the proof says false, the bug is real.

---

🦬☀️ *Sol is a Lean 4 verification framework for deterministic hardware and the software that runs on it. Timed session types are part of Sol.Lib.TimedSession. [GitHub](https://github.com/modelmiser/sol).*
