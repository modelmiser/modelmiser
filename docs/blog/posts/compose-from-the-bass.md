---
date: 2026-04-04
---

# Compose From the Bass

Why "know your bottleneck" isn't enough, and what a metal bassist accidentally teaches about GPU programming.

<!-- more -->

Steve Harris has written Iron Maiden's music since 1975 — five decades on the
same bass, in the same band, with the same compositional method. That
consistency has a direct structural analog in how expert practitioners design
for GPUs, FPGAs, and CPUs, and the connection goes deeper than "know your
bottleneck."

The standard advice is: profile your code, find the bottleneck, optimize it.
This is correct and insufficient. It describes one of three structurally
distinct operations, and confusing them costs an order of magnitude.

## Three operations that look the same and aren't

**Optimize FOR the bottleneck.** You write the algorithm. You profile it. You
discover cache misses, routing congestion, or memory bandwidth saturation. You
patch: add prefetch hints, place critical cells manually, restructure a loop.
The composition was designed from the conventionally-dominant layer — the
compute, the logic, the algorithm — and the binding constraint gets remedial
attention afterward.

Harris analog: write the guitar riff, realize the bass can't keep up, simplify
the bass part.

**Optimize AT the bottleneck.** You know the constraint in advance. You
hand-tune the critical path: carefully designed memory access patterns in the
inner loop, manual floorplanning of timing-critical modules, hand-written SIMD
intrinsics. The overall architecture was still conceived top-down from the
conventional layer, but the hot path gets expert treatment.

Harris analog: write the song guitar-first, but craft the bass line in the
chorus because you know the low end carries the energy there.

**Compose FROM the bottleneck.** The binding constraint is where the design
*originates*. You don't write the algorithm and fit it to memory — you look at
what the memory hierarchy can naturally express, and the algorithm falls out as
a consequence. You don't write the logic and hope it routes — you look at what
the routing fabric wants, and the logic follows.

Harris: the bass line is written first. It carries melody and harmony. The
guitars harmonize above it, doubling or filling space the bass leaves open.
The compositional origin IS the binding constraint.

The difference between operations two and three is not optimization intensity.
It's design freedom. When you compose FROM the constraint, you discover
solutions invisible from the conventional vantage point — solutions that don't
look like optimized versions of the obvious approach. They look like entirely
different designs.

These blur in practice — most real engineering lives somewhere on the
continuum. The distinction is about where design authority originates, not
about strict categories. But the endpoints are qualitatively different, and
most practitioners underestimate how far apart they are.

## The claim

Compose-FROM produces designs that are largely unreachable by iterative
refinement of compose-conventionally designs. Not always mathematically
disjoint — but practically, the path from one to the other is long enough that
nobody walks it.

This is falsifiable. If every compose-FROM design can be reached by sufficient
optimization of a conventional starting point, the principle reduces to
"optimize harder." Three cases where it cannot:

**Cache-oblivious algorithms.** Funnelsort (Frigo et al., FOCS 1999)
recursively divides work into subproblems that automatically fit whatever
cache level they land in — without knowing cache sizes at compile time. You
don't arrive at funnelsort by optimizing a conventional sort. The recursive
k-way merge structure that produces automatic cache adaptation has no analog in
flat two-way mergesort. The algorithm's shape mirrors the cache hierarchy's
recursive structure because it was composed from that structure.

**CUTLASS.** NVIDIA's template library for matrix operations on GPU structures
everything around tiles — chunks of data that fit in shared memory. You don't
write a triple nested loop and tile it afterward. You start from the tile shape
the memory hierarchy dictates, and compose the computation to fill those tiles.
The multistage pipeline interleaves global memory loads with shared memory
computation — the algorithm's structure mirrors the memory pipeline's structure,
not the mathematical operation's structure. A naive CUDA GEMM that already uses
shared memory but without careful tiling leaves an order of magnitude on the
table compared to CUTLASS on an A100. A truly naive triple loop leaves two.

**Carry-chain-first arithmetic on ECP5.** On a Lattice ECP5, each SLICE
contains LUT4s, flip-flops, and a carry chain. Write `a + b + c + d`
behaviorally and Yosys may synthesize a multi-level adder tree with long
routing between levels — timing closure suffers. Compose from the carry chain
instead: structure the additions as parallel carry-chain columns feeding a
third.

```verilog
// Composed from ECP5 carry chain structure:
// two parallel adds in adjacent SLICEs, then combine
wire [15:0] sum_ab, sum_cd;
assign sum_ab = a + b;  // carry chain in column N
assign sum_cd = c + d;  // carry chain in column N+1
assign result = sum_ab + sum_cd; // carry chain in column N+2
```

The logic is physically contiguous. Timing closure improves substantially —
same function, better frequency, because the RTL's structure reflects the
fabric's structure rather than the arithmetic's structure.

## A spectrum

At **Scale 0**, you ignore the constraint. Write the math, let the compiler
deal with it. Most software lives here. On a GPU, a naive matrix multiply
achieves single-digit percentages of peak throughput — the compute units sit
idle, starved for data.

At **Scale 1**, you compose from the constraint. Memory-first GPU kernels.
Routing-first FPGA floorplans. Data-Oriented Design on CPUs, where you ask
"what does the cache line want?" and let the data layout answer. This is where
the 10-100x gains live.

At **Scale 2**, you co-evolve the constraint and the composition — which
requires controlling the hardware. Apple's M1 unified memory didn't optimize
for the existing hierarchy; it reshaped the hierarchy to better serve as spine
for CPU, GPU, and Neural Engine simultaneously. NVIDIA's Tensor Cores aren't generic ALUs tuned for matrices; they're
fixed-shape matrix-multiply-accumulate units whose dimensions match the tile
shapes the memory subsystem can feed. Xilinx Versal's Network-on-Chip replaces
conventional
FPGA routing for bulk data movement entirely — swapping the constraint for a
purpose-built spine. Scale 2 is where paradigm shifts happen, but it requires
silicon-level agency.

At **Scale 3**, the constraint becomes the design language itself. In Halide
(widely used in production at Google and Adobe), expert practitioners report
thinking entirely in schedules — the memory hierarchy's structure IS the
program. Polyhedral compilation (as in LLVM's Polly, though it remains more
research tool than production workhorse) takes this further: loop nests become
integer polyhedra optimized for the target cache hierarchy directly. Powerful
but domain-restricted: this works for stencil computations and regular loop
nests, not for graph algorithms or irregular control flow.

The sweet spot for most practitioners is Scale 1 with awareness of Scale 2.

## The detection problem

Harris knows bass is the spine because he's holding one. His detection cost is
zero — it's baked into his identity as a musician. This is more useful than it
sounds.

There are three ways to identify the binding constraint:

**Post-hoc profiling.** Build it, measure it, discover. Nsight Compute,
nextpnr timing reports, `perf stat`. Accurate but late — you've already
written the code by the time you learn what constrains it.

**Analytical modeling.** Calculate first. The roofline model: compute the
kernel's arithmetic intensity (FLOPS per byte transferred), compare it to the
machine's compute-to-bandwidth ratio. Below the line: memory-bound. Above:
compute-bound. For FPGAs: count your multiplies against the DSP budget, state
bits against BRAM, and check the routing estimate. Cheap, approximate, and
sufficient to reach Scale 1.

**Instrument identity.** A GPU programmer who hears "matrix multiply" and
immediately thinks in tiles and shared memory capacity. An FPGA designer who
hears "add two numbers" and thinks in carry chains and SLICE columns. They
compose from the constraint because that's how they *see* computation. You
don't train yourself into this — you practice until the constraint's
perspective becomes your default perspective.

This suggests a tool design principle worth taking seriously: the default view
should be the binding constraint's perspective, not the conventional
hierarchy's. Nextpnr's GUI shows logic by default and routing on request.
NVIDIA Nsight shows compute utilization with memory as a secondary panel.
Inverting those defaults — routing congestion as primary view, memory timeline
as primary view — would nudge every user toward compose-FROM thinking without
requiring years of expertise first.

## Where it fails

Three honest failure modes:

**Constraint shift.** A kernel that's memory-bound for small matrices and
compute-bound for large ones. Composing from memory optimizes for one regime.
CUTLASS handles this with compile-time template selection per problem
shape — multiple bass lines, chosen at dispatch time.

**Balanced designs.** At the exact roofline knee — neither memory nor compute
dominates — there is no clear bass. The principle gives no guidance. This is
rarer in practice than in theory, because most real workloads sit clearly on
one side, but it's the genuine theoretical limit.

**Unknowable constraints.** Graph traversal, sparse linear algebra, tree
search — problems where the memory access pattern depends on data not available
at design time. You can't compose from a constraint you can't predict. GPUs
handle this with warp-level parallelism to amortize what they can't
optimize — a fundamentally different strategy.

Auto-tuning frameworks like Triton and TVM partially automate the Scale 0 to
Scale 1 transition by searching tile configurations programmatically. This is
genuine and valuable — but the search is within a fixed algorithmic template.
Auto-tuners can find good tiles for your GEMM. They won't discover funnelsort.

Harris works because his constraint is unambiguous. He's holding the bass. When
your constraint is ambiguous or shifting, you need a different model. But for
the majority of computational workloads where one constraint clearly
dominates — and most do — compose-FROM is the difference between 5% and 90%
of what the hardware can deliver.

That's not "optimize harder." That's picking up the bass.

---

🦬☀️ *Cross-domain observation from the [warp-core](../../research/warp-core.md) FPGA project
and [warp-types](../../research/warp-types.md) GPU type system.
[GitHub](https://github.com/modelmiser).*
