# warp-core

A soft GPU on the ECP5-85F FPGA: 4 SIMT warps in a D4 Corner Grid with 9 super-J1
Forth cores, auto-diverging branches, and runtime-loadable virtual peripherals.

**Status:** ISA v0.5.2 spec complete. Corner Grid topology committed. 4-lane warps with SHFL, FMUL, deep stacks. Mandelbrot rendering verified on hardware at 33 MHz.

**Repository:** [github.com/modelmiser/warp-core](https://github.com/modelmiser/warp-core) (not yet public)

## What it is

A processor you can understand end-to-end on a single FPGA board. Four 4-lane SIMT
warps at the corners of a 3×3 mesh of J1 Forth cores — deterministic stack machines
communicating through single-cycle CSP channels. Each warp has hardware divergence,
lane shuffles, reductions, and 32×32 fixed-point multiply. HDMI output for immediate
visible results.

Each warp can run a different *personality* — a piece of microcode that acts as a
virtual peripheral (display renderer, audio synthesizer, sensor poller, protocol
bridge). The J1 mesh coordinates warp lifecycles, routes data, and provides a
formally-verifiable control fabric with cycle-accurate timing.

## Blog posts

<!-- blog-posts:warp-core -->
