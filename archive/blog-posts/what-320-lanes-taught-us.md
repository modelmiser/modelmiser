---
date: 2026-04-14 18:00:00
categories:
  - warp-core
---

# What 320 Lanes Taught Us About 4

When you can't fit what you want, remove the thing that seems like it's helping.

<!-- more -->

## The coin-flip builds

warp-core is a soft GPU on a Lattice ECP5-85F. Four SIMT warps — originally eight lanes each, 32 lanes total — targeting a hobbyist FPGA board. The architecture recently pivoted from dual VexRiscv RISC-V cores to a J1 Forth mesh — nine stack-machine cores in a 3×3 grid, with SIMT warps attached at the corners. The VexRiscv cores were fast (150 MHz) but opaque: pipelined, cached, non-deterministic. The J1 is the opposite — roughly 200 lines of Verilog, one instruction per cycle, fully deterministic, and it maps directly to Chuck Moore's GA144 tradition of minimal Forth cores communicating through channels. The mesh gives warp-core a coordination fabric where every cycle is accounted for and every channel operation has a provable timing. The warps had been growing features for weeks — hardware multiply, shuffle crossbar, deeper stacks, subroutine call depth — and then they stopped fitting.

The synthesis reports told the story: 101-105% TRELLIS_COMB utilization. Every build was a coin flip. ABC, the logic optimizer inside Yosys, is non-deterministic — different runs produce different gate counts for the same input, and when you're at 101% the difference between "routes" and "doesn't route" is which way the optimizer's internal random seed fell. Some builds closed. Some didn't. None were reliable.

The obvious fix: remove features until it fits. Disable SHFL (the inter-lane shuffle network). Disable FMUL (32x32 multiply with built-in shift). Shrink stacks from 8 to 4. Shrink subroutine depth from 4 to 2. Disable hardware multiply entirely and fall back to software. Each feature gate drops a few thousand LUTs. Stack enough gates and you're back under budget.

This works. It produces a warp with 8 lanes that can't do anything interesting with them.

Eight lanes with no shuffle is eight independent calculators that happen to share a program counter. They can't exchange data. They can't cooperate on a reduction. They can't broadcast a result from one lane to the others. The only communication path is through SDRAM — write from one lane, read from another — which costs hundreds of cycles per exchange and destroys the entire performance model. Eight lanes without SHFL is not "a GPU with wide warps." It's a waste of silicon area that could have been something else.

## The subtraction that adds

Drop from 8 lanes to 4. Each warp pipeline shrinks. The shuffle crossbar goes from 8x8 (64 multiplexer inputs) to 4x4 (16). The register file halves. The divergence stack narrows. The store drain serializer that was 8-lane wide becomes 4-lane wide. The cumulative savings: from 101-105% utilization down to roughly 71%.

Twenty-nine percent headroom. Enough to re-enable everything.

SHFL comes back — inter-lane shuffle for scan, reduce, broadcast, butterfly exchange. FMUL comes back — 32x32 multiply with a shift stage, essential for fixed-point graphics. Stacks go to 8 deep. Subroutine call depth goes to 4. Hardware multiply stays on. Five gated features, all re-enabled, because removing 4 lanes from each warp freed more resources than all five features consume.

The 4-lane warp with all features enabled is a more capable processor than the 8-lane warp without them. This isn't a tradeoff. It's a Pareto improvement hiding behind the assumption that wider is better.

## Why shuffle changes everything

The specific feature that makes this a qualitative shift, not just a quantitative one, is SHFL.

Four lanes without shuffle: four independent computations that execute in lockstep but cannot see each other's registers. Any algorithm that requires inter-lane communication — reductions, prefix sums, broadcasts, data-dependent exchanges — must go through memory. At warp-core's SDRAM bandwidth, a single inter-lane exchange costs roughly 40-60 cycles through the store-drain and load-drain FSMs. A butterfly reduction across 4 lanes requires log2(4) = 2 exchange stages, so 80-120 cycles.

Four lanes with SHFL_XOR: the same butterfly reduction is 2 instructions, 2 cycles. The shuffle crossbar moves 32-bit values between any pair of lanes in a single clock. That's a 40-60x speedup on the primitive operation that parallel algorithms are built from.

The Mandelbrot renderer makes this concrete. Each warp processes a row of pixels, 4 at a time — one per lane. Each lane iterates z = z^2 + c independently until |z|^2 exceeds the escape threshold. But the lanes escape at different iterations: a pixel deep inside the set may need all 64 iterations while its neighbor escapes at iteration 3. Without cooperation, every lane must run for max_iter iterations. With SHFL-class cooperation, the BANY instruction — "branch if ANY lane's predicate is true" — lets the warp exit the inner loop the moment no lane still needs work.

The pattern: each lane computes an escape flag. A CMOV (conditional move) latches the iteration count on first escape, so the result is preserved even after the lane stops contributing. BANY checks the complement — "is any lane still iterating?" — and loops only while at least one lane has work to do. When the last lane escapes, the entire warp drops out.

This is not a clever optimization layered onto an existing design. It's a fundamentally different execution model. The lanes cooperate: they observe each other's state (through BANY's implicit reduction of all lane predicates) and make collective decisions. BANY is a 1-cycle warp-wide OR-reduction — the cheapest possible cooperative primitive, and it only exists because the shuffle/reduction infrastructure is enabled. Without SHFL, BANY doesn't exist. Without BANY, every lane pays for the slowest lane's iteration count. The difference in render time is roughly 3x for a typical Mandelbrot viewport, because most pixels escape early and only the set boundary needs full iteration depth.

Combined across the [full optimization stack](120x-in-an-afternoon.md): hardware multiply (18x), 4-warp parallel rendering (4x), PLL boost from 20 to 33 MHz (1.67x). Product: roughly 120x. Sub-frame render at 60 Hz. The 120x is not about any one change — it's about the fact that the 4-lane decision unlocked the feature set that made the other multipliers accessible.

## The Groq parallel

Groq's Tensor Streaming Processor (now marketed as the LPU, Language Processing Unit) has 320 lanes per superlane, 20 superlanes, and 409,600 MAC units on a single die (per the ISCA 2020 architecture paper). It is arguably the most radical production chip architecture of the last decade, and the load-bearing decision was a subtraction.

The TSP has no caches. No branch prediction. No register files. No off-chip HBM. Instead: 230 MB of on-chip SRAM, directly addressed, with deterministic access at every cycle. The compiler — built before the chip existed — schedules every memory access at compile time. There is nothing to predict because nothing is speculative.

The energy argument is stark: on-chip SRAM costs roughly 0.3 picojoules per bit access. Off-chip HBM costs roughly 6 picojoules per bit. That's a 20x energy advantage per memory operation. For inference workloads that are memory-bandwidth-bound (which is most of them), the 20x on memory access dominates everything else in the power budget.

But Groq didn't get to 230 MB of on-chip SRAM by adding it alongside HBM. They got there by removing HBM entirely and reclaiming the die area, the power budget, the I/O pins, and the packaging complexity that HBM would have consumed. The subtraction — no external memory — is what made the addition — massive on-chip SRAM — physically possible.

The structural parallel with warp-core's lane reduction is striking. Groq removed the memory hierarchy that every other AI chip considers essential and discovered that the resource it freed — die area, power, I/O bandwidth — could fund something better. We removed 4 lanes per warp that the GPU design pattern considers essential and discovered that the resource freed — LUTs, routing, timing margin — could fund something better. In both cases, the resource you think is helping (more lanes, external memory) is the resource that's gating the capability that actually matters (feature depth, on-chip bandwidth).

The compiler-first methodology reinforces the point. Groq built the software toolchain before taping out silicon, which meant they could verify that deterministic scheduling was sufficient before committing to a cacheless architecture. Warp-core built the assembler and ISA simulator before committing to 4-lane warps, which meant we could verify that SHFL + BANY cooperation patterns worked at width 8 before cutting lanes. In both cases, the software proved the subtraction was safe before the hardware committed to it.

## The other end of the curve

Chuck Moore's GA144 — Greenarrays' 144-core Forth chip — pushes the same principle to its logical extreme. Each core is 18 bits wide with 64 words of RAM and a 10-deep data stack. No interrupts. No caches. No bus. Communication is synchronous blocking rendezvous between adjacent cores on an 18x8 grid.

Moore didn't arrive at 144 cores by asking "how many cores can we fit?" He arrived there by asking "how simple can each core be?" The answer — a stack machine that executes 4 instructions per word, with an ALU barely wider than a single data path — freed enough silicon area for 144 of them. The width of each core (18 bits, not 32 or 64) is the subtraction. The core count is the consequence.

Three architectures, three points on the same curve. The GA144 lives at the extreme of core simplicity — 1-instruction-wide, 18-bit, 144 copies. The TSP lives at the extreme of memory hierarchy simplicity — no caches, no external memory, deterministic scheduling. Warp-core's Corner Grid lives somewhere in the middle — 4 lanes per warp instead of 8, but with a feature set per lane that makes each lane individually more capable.

The curve itself is the insight: width and depth are fungible resources in any fixed silicon budget. Wider processors with fewer features. Narrower processors with more features. The total capability — what the system can actually compute, not what its peak lane count suggests — depends on which point on the curve matches the workload. For the Mandelbrot renderer, 4 cooperating lanes outperform 8 independent ones. For Moore's asynchronous signal processing, 144 trivial cores outperform any achievable single core. For Groq's inference engine, deterministic on-chip memory outperforms speculative off-chip memory. Each chose the right point by subtracting the right thing.

## Topology as proof

The Corner Grid topology survived the lane reduction intact: 4 warps at the four corners of a 3x3 super-J1 Forth mesh, D4 (dihedral group of order 8) rotational symmetry preserved. The "pinwheel" layout — each warp attached from a different cardinal direction under 4-fold rotation — means any kernel that works on one warp works on all four under rotation, and any J1 routing pattern that works in one quadrant works in all four.

Four warps at 4 lanes each: 16 total lanes. The same compute budget as 2 warps at 8 lanes each — but with 4 independent program counters instead of 2, meaning 4 independent program streams that can execute different kernels simultaneously. The 4-warp configuration has strictly more scheduling flexibility than any 2-warp configuration with the same total lane count.

And the 29% LUT headroom isn't idle. It's where the 9-core J1 Forth mesh lives — the control plane that orchestrates the warps, manages the display, handles I/O, and provides an interactive Forth REPL. The lanes we removed became the cores that make the remaining lanes useful.

## The diagnostic

There's a reliable signal for when you're in this situation. It's not "the build doesn't fit" — that's too late. The signal is: **you have a resource that looks essential but that you're spending effort to disable features around.**

If you're gating features to accommodate width, the width isn't helping. If you're adding caches to accommodate external memory, the external memory isn't helping. If you're adding complexity to accommodate simplicity, something has inverted.

The fix is always the same shape: remove the thing that looks like it's helping. Count what you get back. Spend it on what you actually need.

Groq got a 20x energy advantage and deterministic scheduling. Moore got 144 cores. We got a soft GPU that fits on a hobbyist FPGA board with room for a Forth mesh beside it. Different scales, different domains, same subtraction.

---

🦬☀️ *[warp-core](../../research/warp-core.md) is an open-source soft GPU on ECP5-85F FPGA. 4 SIMT warps in a Corner Grid with 9 super-J1 Forth cores. [GitHub](https://github.com/modelmiser/warp-core).*
