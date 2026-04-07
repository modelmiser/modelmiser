# warp-core

A soft GPU on the ECP5-85F FPGA: 4-warp, 8-lane SIMT with cooperative scheduling,
auto-diverging branches, and runtime-loadable virtual peripherals.

**Status:** ISA v0.5.2 spec complete (95 instructions, 29 CSRs). RTL migration in progress.

**Repository:** [github.com/modelmiser/warp-core](https://github.com/modelmiser/warp-core) (not yet public)

## What it is

A processor you can understand end-to-end on a single FPGA board. Four independent SIMT
pipelines, each running 8 lanes, with a hardware divergence stack, lane shuffles,
reductions, and inter-warp channels. HDMI output for immediate visible results.

Each warp can run a different *personality* — a piece of microcode that acts as a
virtual peripheral (display renderer, audio synthesizer, sensor poller, protocol
bridge). A RISC-V kernel dispatches and manages warp lifecycles from Rust firmware.

## Blog posts

<!-- blog-posts:warp-core -->
