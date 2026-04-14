---
date: 2026-04-14 14:00:00
categories:
  - warp-types
---

# Intervals Collapse to Points

What happens to formal verification when the hardware is deterministic.

<!-- more -->

## What this post needs you to know

**Session types** are types that describe communication protocols — what gets sent, in what order, between which endpoints. Protocol violations become type errors at compile time. **Timed session types** add clock annotations to each action: "this send occurs at cycle 3." On non-deterministic networks those clocks are intervals, and verifying them is a constraint-solving problem. On **deterministic hardware** — where every instruction and channel has a known cycle cost — the intervals collapse to points, and so do the proofs. The sections below walk through what that collapse actually changes.

## The timing problem in session types

Session types describe the shape of communication: this endpoint sends an integer, then receives a boolean, then terminates. The type system guarantees that two endpoints follow complementary protocols — if one sends, the other receives. No runtime check needed. The compiler enforces it.

Bocchi, Yang, and Yoshida extended this to time. Their timed multiparty session types (CONCUR 2014) add clock constraints to each action: "this send occurs at time t where t lies in the interval [a, b]." The target is distributed systems where network latency varies. A message sent at time 3 might arrive at time 5, or 7, or anywhere in between. The type system must reason about whether the receiver's window overlaps the sender's delivery window, whether deadlines are satisfiable given the timing constraints of all other participants, and whether the entire protocol can be scheduled without deadlock.

This requires constraint solving over clock zones — the same machinery as timed automata model checking. Clock zones are convex polyhedra over clock differences, and the satisfiability problem is PSPACE-complete in the worst case. Bocchi's system handles this through a type-level consistency check that decides whether the conjunction of all participants' timing constraints is satisfiable. Practical, but expensive. The proofs are existential: show that SOME schedule satisfying all constraints EXISTS.

On deterministic hardware, the question changes.

## What determinism buys

On a Groq Tensor Streaming Processor, every instruction has a known cycle cost. On our J1 Forth mesh — nine cores in a 3×3 grid on an ECP5 FPGA, connected by single-cycle CSP channels — every instruction also has a known cycle cost. Channel latency is a fixed constant: 1 cycle from core to core, always, not a distribution. The compiler doesn't need to ask "could this message arrive between cycle 47 and cycle 52?" It computes "this message arrives at cycle 48."

The qualitative shift isn't that proofs become easier. It's that the KIND of proof changes.

**Timing consistency.** Bocchi needs to show that timing constraints across a channel are satisfiable — an existential claim requiring constraint solving. On deterministic hardware, the sender's cycle and the receiver's cycle are both compile-time constants. Timing consistency reduces to an equality: `recv_cycle = send_cycle + latency`. In Lean 4, this is `rfl` — reflexivity, the simplest possible proof term. The type checker confirms it without invoking any tactic engine.

**Deadlock freedom.** In a non-deterministic system, proving no execution leads to deadlock requires inductive reasoning over all possible interleavings. On deterministic hardware, there is exactly one execution. Deadlock freedom becomes: simulate the system for N cycles, check that no state has both cores blocked with no data in flight. In Lean 4, this is `native_decide` — compile the simulation to native code, run it, check the boolean result. The proof kernel trusts the computation. For our 12-step ping-pong protocol, this takes 294ms.

**Termination.** Same story. Non-deterministic termination requires bounded liveness arguments: show that progress occurs within some bound under all schedules. Deterministic termination is `native_decide` again: run the system, check that both cores halt.

**Schedule optimality.** In a non-deterministic setting, finding the optimal schedule is a search problem — heuristic at best, NP-hard at worst. On deterministic hardware, the schedule IS the program. A SAT solver can find whether a schedule meeting given constraints exists, and if it does, Lean 4 verifies the resulting program's timing properties computationally. Search produces the candidate; the proof kernel certifies it.

These are not four incremental improvements. They're a categorical change. Intervals collapse to points. Constraint satisfaction collapses to equality checking. Inductive arguments over interleavings collapse to computation over a single trace.

## The worked example

Two J1 cores, ping-pong. Core 0 computes for three cycles, sends a value on the forward channel, waits for a response. Core 1 waits for that value, computes for two cycles, sends the result back. Both channels have latency 1.

Bocchi's framework would type the forward channel like this:

```text
∃ t, t ∈ [send_time + L_min, send_time + L_max]
     ∧ recv_ready(t)
     ∧ ∀ t' < t, ¬recv_ready(t')
```

The type system must show that the receiver's ready window overlaps the delivery window. With variable latency (`L_min` to `L_max`), this is a constraint satisfaction problem. The proof witness is a specific time `t` in the intersection of two intervals, plus evidence that the receiver is actually ready at that time.

Our framework types the same channel:

```lean
theorem fwd_timing : send_recv_consistent 3 4 fwd_channel := by
  unfold send_recv_consistent fwd_channel
  rfl
```

Core 0 sends at cycle 3. The channel has latency 1. Core 1 receives at cycle 4. The proof is `rfl`: 4 = 3 + 1. Lean's kernel confirms this by computation. No constraint solver. No existential witness. No search.

The full protocol verification — timing consistency on both channels, deadlock freedom across all 12 steps, termination of both cores — is 11 theorems. Every timing proof is `rfl`. Every behavioral property is `native_decide`. The entire proof suite checks in under a second.

```lean
-- Timing: rfl
theorem fwd_timing : send_recv_consistent 3 4 fwd_channel := by
  unfold send_recv_consistent fwd_channel; rfl

theorem rev_timing : send_recv_consistent 7 8 rev_channel := by
  unfold send_recv_consistent rev_channel; rfl

-- Deadlock freedom: native_decide (simulate all 12 steps)
theorem deadlock_free_all_steps :
    TwoCoreSystem.all_safe pingPongProgram 12 = true := by native_decide

-- Termination: native_decide
theorem system_terminates_at_10 :
    (run 12).terminated := by
  unfold TwoCoreSystem.terminated; native_decide
```

The `rfl` proofs and the `native_decide` proofs are qualitatively different objects. `rfl` is the type checker recognizing that two terms compute to the same value — it doesn't even enter the tactic framework. `native_decide` compiles the proposition to native code, evaluates it, and feeds the boolean result back to the kernel. Both exploit the same hardware property: every value is a compile-time constant, so every question about the system's behavior reduces to computation.

## The energy parallel

The same principle — determinism enables optimization — shows up in the energy domain. Groq's TSP keeps all data in on-chip SRAM. The energy cost of an on-chip SRAM access is roughly 0.3 pJ/bit. An off-chip HBM access costs roughly 6 pJ/bit — a 20x penalty. GPUs pay this penalty on every cache miss, and the frequency of cache misses depends on the workload, the cache replacement policy, and the memory access pattern. It's non-deterministic at the hardware level.

Groq's deterministic scheduling eliminates cache misses entirely. There is no cache. The compiler places every datum in a specific SRAM location at a specific cycle. The energy profile is as predictable as the timing profile — both are consequences of the same architectural decision.

This matters for formal verification because energy bounds become provable too. If every memory access is statically known, and every access hits SRAM at 0.3 pJ/bit, the total energy cost of a program is a compile-time constant. On a GPU, energy cost is a statistical distribution. The same "intervals collapse to points" phenomenon applies: energy intervals on non-deterministic hardware become energy points on deterministic hardware.

## Where this sits in the literature

Bocchi, Yang, and Yoshida's "Timed Multiparty Session Types" (CONCUR 2014) established the theory. Their clock constraints handle the general case — non-deterministic networks where latency varies — and the type system is sound. The proofs are pen-and-paper.

Recent work has brought session types into proof assistants — mechanized duality, progress, and type preservation proofs in Coq (2024-25). But that work handles untimed session types on abstract systems, not timed types on physical hardware.

To our knowledge, no prior work connects timed session types to deterministic hardware in a proof assistant. The theory exists (Bocchi). The hardware exists (Groq's TSP, our J1 mesh). The proof framework exists (Sol on Lean 4). The connection between them — that hardware determinism collapses the proof obligations from constraint solving to reflexivity — is what we're demonstrating.

The three-core spine proof extends this further. J10 sends to J11, which routes the data to J12, which computes and sends back. Three cores, four channels, 20 simulation steps. D4 symmetry of the mesh means the four corner bridge proofs reduce to one proof plus three trivial instantiations. The compositionality is structural: each channel pair gets its own timing proof, and the only coupling between channels is at shared cores.

## The scalpel

The vision beyond the J1 mesh is what we call "deterministic islands."

A GPU is non-deterministic. Memory latency varies. Warp scheduling varies. Cache behavior varies. But within a single warp, if three conditions hold, the execution is deterministic: warp-types proves no divergence (all lanes execute the same path), data stays in registers or shared memory (no global memory latency variance), and the warp is pinned to one SM (no cross-SM scheduling variance).

Under those three constraints, a fragment of GPU execution has the same timing properties as the J1 mesh. Timed session types apply to it. The type system is the scalpel that carves deterministic regions from non-deterministic substrates — and within those regions, the same `rfl` proofs work.

Groq's compiler exploits determinism by producing statically-scheduled programs and asserting correctness. The assertion is a compiler invariant: if the compiler is correct, the schedule is correct. Our approach proves correctness with machine-checked Lean 4 theorems. The assertion trusts the compiler. The proof trusts only the Lean kernel.

Same hardware property. Different trust model. The interval collapsed to a point either way — the question is whether you believe it because someone told you, or because you checked.

---

🦬☀️ *Sol is a Lean 4 verification framework for deterministic hardware and the software that runs on it. Timed session types are part of Sol.Lib.TimedSession. [GitHub](https://github.com/modelmiser).*
