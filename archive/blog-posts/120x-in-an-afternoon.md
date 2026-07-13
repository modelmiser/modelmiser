---
date: 2026-04-13 16:00:00
categories:
  - warp-core
---

# 120x in an Afternoon

Three multiplicative improvements that each looked trivial on their own.

<!-- more -->

## The starting point

Warp-core's Mandelbrot renderer ran on a single 8-lane SIMT warp at 20 MHz. One warp of four, software multiply, conservative clock. The frame — 320x240, Q4.12 fixed-point, 16 iterations max — took roughly 3 seconds to render. Adequate for proving the pipeline works. Not adequate for anything interactive.

Three changes, each independently small, combined to 120x. The frame time dropped from 3 seconds to about 25 milliseconds — sub-frame at 60 Hz. None of the three required new hardware. All three exploited resources that were already synthesized, already paid for in LUTs and routing, and already sitting idle.

The pattern that connects them is worth more than the speedup.

## Improvement 1: hardware multiply (18x)

The Mandelbrot inner loop computes `z = z*z + c` in complex fixed-point. Each iteration requires three multiplies: `x*x`, `y*y`, and `x*y`. The firmware was calling a software multiply subroutine — 55 lines of shift-and-add, approximately 128 instructions per invocation. Three calls per iteration: roughly 400 instructions of multiply per Mandelbrot step.

The replacement: `mul16 r, r, r` followed by `sari r, r, 12` to rescale the Q4.12 result. Two instructions. Per multiply, that's 128 instructions down to 2 — a 64x reduction per call. Across the three multiplies per iteration, the instruction count drops from ~400 to 6.

But the speedup isn't 64x, it's 18x. The reason: the software multiply wasn't the only thing in the loop. There's the escape-radius check, the iteration counter, the pixel write, the coordinate setup. Those instructions don't shrink. The multiply consumed roughly 96% of per-pixel compute; eliminating it exposes the 4% that was always there. Amdahl, as usual, gets the last word.

Here's what makes this one sting: the DSP blocks were already instantiated. Every warp in the design had `ENABLE_MUL=1` set at synthesis time. The ECP5-85F's DSP slices — `MULT18X18D` primitives, one per lane — were placed, routed, and consuming static power. The firmware just wasn't issuing the instruction that used them.

This is the FPGA equivalent of buying a GPU and running everything on the CPU. The silicon was allocated. The routing was done. The only thing missing was a two-instruction sequence in the inner loop.

## The DSP budget question

Why `mul16` and not `fmul`? The ISA offers both. `mul16` is a 16x16-bit signed multiply producing a 32-bit result, consuming one DSP slice per lane. `fmul` is a full 32x32-bit multiply, requiring 2-4 DSP slices per lane depending on how the synthesizer decomposes it.

The Mandelbrot operands are Q4.12 fixed-point: 4 integer bits, 12 fractional bits, signed. The representable range is [-8.0, +7.999755859375]. The operands always fit in 16-bit signed. There is no reason to use a wider multiply.

The budget math makes this concrete. The ECP5-85F has 156 DSP slices total. With `mul16` at 1 DSP per lane: 4 warps times 8 lanes times 1 DSP = 32 DSPs for multiply across all warps. Comfortable — 20% of the budget, leaving 124 for the SDRAM controller, display pipeline, and future use.

With `fmul` at 2 DSPs per lane (optimistic): 4 times 8 times 2 = 64 DSPs. Tight but feasible. At 4 DSPs per lane (pessimistic Yosys decomposition): 128 DSPs. That's 82% of the chip's entire DSP budget, leaving 28 for everything else. The SDRAM controller alone needs several.

Use the narrowest multiply that covers your value range. This isn't a novel principle — it's standard DSP engineering practice dating back to fixed-point signal processing in the 1970s. But on an FPGA where DSP slices are a hard physical limit, the difference between "fits" and "doesn't fit" is binary. There's no graceful degradation when you run out of DSP primitives. The synthesizer fails.

## Improvement 2: four-warp row partitioning (4x)

The Mandelbrot computation is embarrassingly parallel per pixel. Per row, even. The only serialization constraint is the palette: a 4-write MMIO sequence that programs the color lookup table, and those writes can't interleave through the crossbar arbiter without corrupting the palette state.

The partition: warp 0 programs the palette exclusively, then all four warps divide the 240 rows. Each warp computes `start_row = warp_id * 60` via the `warp_id` intrinsic and renders 60 rows. The framebuffer is partitioned by address range — warp N writes to rows [60*N, 60*(N+1)) — so there are no write conflicts.

Scaling is near-linear because the work per row is independent and roughly uniform (the Mandelbrot set's compute intensity varies by region, but averaged over 60 rows the variance is low enough). Four warps, 4x throughput.

With hardware multiply freeing up instruction budget, `max_iter` went from 16 to 64 — a 4x increase in escape-band resolution. The Mandelbrot boundary went from blocky 16-color contours to smooth 64-level gradients. The extra iterations cost compute, but the 18x multiply speedup had bought far more headroom than the finer iterations consumed.

186 of 256 available instruction words in use in the final firmware. The kernel fits, but barely. Every instruction earned its slot.

## Improvement 3: PLL boost, 20 to 33 MHz (1.67x)

This one is a single parameter change: `CLKOP_DIV` from 25 to 15 in the ECP5 PLL configuration. The VCO runs at 500 MHz regardless. Dividing by 25 gives 20 MHz. Dividing by 15 gives 33.3 MHz.

The LPF constraint file — the timing specification that tells the place-and-route tool what frequency to target — already said 33 MHz. The nextpnr runs were already closing timing at 33 MHz. The synthesis, placement, and routing had been optimized for a clock speed that the PLL wasn't actually generating.

The constraint and the clock lived in different files. The LPF file said "target 33 MHz." The PLL instantiation said "generate 20 MHz." Nobody noticed the 67% gap because the design worked — slowly — and there was no automated check that the PLL output frequency matched the timing constraint.

One line. 1.67x.

## The same pattern twice

The PLL sandbagging is structurally identical to the DSP waste. In both cases, the capability existed in the hardware. The DSPs were synthesized with multiply enabled. The PLL's VCO could produce 33 MHz with a divider change. Both were paid for — in silicon, in routing, in power — and neither was being used.

The DSPs were unused because the firmware predated `mul16` instruction support. The instruction existed in the ISA but the Mandelbrot kernel was written against an older version that lacked it, and nobody revisited the multiply routine after the hardware gained the capability.

The PLL was throttled because 20 MHz was the conservative starting frequency during bring-up. The timing constraints were updated to 33 MHz as the pipeline matured and PNR proved it could close at that speed. The PLL divider wasn't updated because the bring-up configuration was in a different file from the timing constraints, and "it works" is a powerful suppressant of further investigation.

Both are instances of a general failure mode: **the configuration didn't keep up with the capability.** The hardware evolved. The settings that control it didn't. And because the system functioned at the lower performance point, there was no error signal to trigger an audit.

## Audit what you've already paid for

The GPU world has the same problem at a different scale. Shader occupancy — the fraction of an SM's warp slots that are actually executing — is the single most important performance metric in CUDA optimization, and it's routinely below 50% on untuned kernels. The hardware has 64 warp slots per SM. The kernel uses 16 because it allocates too many registers per thread, or because its block size doesn't divide evenly into the SM's capacity. The warps are there. The scheduler can feed them. The kernel doesn't ask for them.

FPGA designs have the equivalent problem with DSP blocks. Many designs synthesize DSPs but use them only as routing fabric — the tools infer `MULT18X18D` primitives for wide multiplexes or address decoding, consuming DSP slices for logic that could run in LUTs. The DSP is "used" in the resource report but isn't doing multiply. On warp-core, the opposite: the DSPs were explicitly instantiated for multiply, correctly configured, correctly routed — and the software was doing the multiply with shift-and-add anyway.

Both directions waste the same resource. One wastes DSPs on non-multiply logic. The other wastes DSP-capable multiply on non-DSP logic. The common root is that the resource allocation and the resource utilization are checked by different people at different times — or, on a solo project, by the same person wearing different hats on different days.

The fix isn't "be more careful." The fix is an audit step: before adding new resources to improve performance, enumerate the resources you've already allocated and check whether they're doing the job they were allocated for. This is boring. It's also where 18x multipliers hide.

## The multiplicative structure

18 times 4 times 1.67 equals approximately 120.

Additive improvements — shaving 10% here, 15% there — are the normal trajectory of optimization. You profile, find the hotspot, reduce it, and the next hotspot is smaller. Diminishing returns are structural. The Pareto frontier approaches asymptotically.

Multiplicative improvements are different. They compose by multiplication, not addition, because they operate on independent axes. Hardware multiply reduces per-pixel instruction count. Multi-warp partitioning increases pixel throughput. Clock boost increases instructions per second. None of these three interacts with the others. Each one's speedup applies to the already-improved baseline from the others. The 4x from multi-warp applies to the 18x-faster pixels, not to the original 1x pixels.

This is only possible because the three bottlenecks were independent. If the multiply speedup had been memory-bound rather than compute-bound, the multi-warp partition would have hit memory contention and scaled sub-linearly. If the PLL boost had caused timing failures, it would have required pipeline changes that interacted with the multiply datapath. Independence is the precondition for multiplicative composition, and independence is not the default — it has to be verified for each pair.

In this case, independence held because the three resources — DSP slices, warp slots, and clock frequency — are physically separate subsystems on the ECP5. The DSPs don't share routing with the warp dispatch logic. The PLL is analog, outside the digital fabric entirely. The design's resource partitioning happened to align with the optimization axes.

That alignment wasn't planned. It was lucky. But recognizing it after the fact is what turned three small changes into a two-order-of-magnitude afternoon.

## What 25 milliseconds enables

At 3 seconds per frame, the Mandelbrot renderer is a static image generator. You set the viewport, wait, and look at the result.

At 25 milliseconds per frame, it's interactive. Pan and zoom at 40 fps. The same hardware, the same FPGA, the same board — running a real-time fractal explorer instead of a batch renderer. The qualitative difference between 3 seconds and 25 milliseconds isn't "faster." It's a different kind of artifact.

The compute was always there. The DSPs were synthesized. The warps were instantiated. The PLL could generate the clock. The afternoon's work wasn't building new capability. It was removing the barriers between existing capability and the code that needed it.

Sometimes the 120x is already on the chip. You just have to look.

*Note: this work was done on the 8-lane warp configuration. The architecture has since moved to [4 lanes per warp](what-320-lanes-taught-us.md) — fewer lanes, but with shuffle, hardware multiply, and deeper stacks re-enabled. The DSP budget numbers above reflect the 8-lane era.*

---

🦬☀️ *[warp-core](../../research/warp-core.md) is an open-source soft GPU on the ULX3S (ECP5-85F). 4 SIMT warps in a Corner Grid with 9 J1 Forth cores. [GitHub](https://github.com/modelmiser/warp-core).*
