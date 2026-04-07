---
date: 2026-04-06 18:00:00
categories:
  - warp-core
---

# The Spec That Ate Its Registers

How a 62-register diagnostic braindump fed itself to an architecture and came out as 9 peripherals.

<!-- more -->

I had a list. Sixty-two diagnostic registers across ten subsystems — clock/PLL health, SDRAM controller state, ECP5 silicon features, memory integrity, bus arbitration, processor pipeline, HDMI output, timing margin, system health, and debug infrastructure. Reasonable items, each individually justified. The kind of spreadsheet you get when you walk through a design and ask "what would I want to observe when this breaks at 2 AM?"

The estimate came to roughly 800-1000 LUTs on an ECP5-85F with 84K available. About 1.2%. Affordable. So the temptation was to wire them up, expose them via UART, and move on.

Instead, the list got fed into a formal architecture — the Virtual Peripheral spec for warp-core's "Keel" system layer. What came out the other side had 9 diagnostic peripherals, not 62 standalone registers. Of the 62 items, 60 were absorbed into those 9 peripherals and 2 were deliberately excluded — a JTAG user register (the UART/protocol path supersedes it) and a generic configurable performance monitor (the spec distributes per-subsystem counters instead). Among the 60 absorbed, 3 didn't survive as registers at all — they were rearchitected into infrastructure the architecture already provided, saving ~160 LUTs. Net cost: ~825 LUTs versus ~985 gross.

The spec didn't describe the registers. It *is* the design. And the difference matters.

## What the architecture absorbs

The Virtual Peripheral pattern in Keel is ruthlessly uniform. Every hardware capability — diagnostic or otherwise — follows the same six-element structure: a register file on the Wishbone bus, minimal glue RTL, Forth words on Core 0 for operation, a Zephyr driver on Core 1 for coordination, protocol commands for remote access, and a manifest entry for discoverability.

Diagnostic peripherals are not special. They are virtual peripherals whose register files happen to observe the system itself rather than driving external interfaces. This is stated in the spec and it is not a platitude — it determines the implementation.

When you take a flat list of 62 registers and ask "which of these observe the same subsystem?", you get clusters. Clock health (PLL lock, clock presence, frequency counters, cross-domain ratio checks) becomes `diag.clk` at ~145 LUTs. SDRAM controller state (read/write counters, refresh monitoring, FSM observation, inflight watchdog, DQ self-test, last-N transaction ring) becomes `diag.sdram` at ~170 LUTs plus one BRAM block. ECP5 silicon features — soft error detection, die temperature, configuration CRC — becomes `diag.ecp5` at ~30 LUTs because the hard IP primitives (SEDFA, DTR) do the real work and you only pay for the register file glue.

Nine peripherals total: `diag.sys`, `diag.clk`, `diag.sdram`, `diag.ecp5`, `diag.mem`, `diag.bus`, `diag.cpu`, `diag.gpdi`, `diag.timing`. The tenth subsystem from the original list — debug infrastructure — didn't become its own peripheral. Its items either landed in `diag.cpu` (breakpoints, PC observation) or were absorbed by the ILA block already specified in the parent architecture. Each with its own priority tier, its own Forth dictionary, its own manifest entry. An AI agent connecting to the system discovers diagnostic capabilities exactly the way it discovers a display controller or a GPIO bank — via `SYS.MANIFEST`.

The clustering isn't the interesting part. Any engineer groups related registers. The interesting part is what the architecture *removes*.

## What the architecture eliminates

Three items from the original plan got rearchitected out of existence. The most expensive was the UART TX dump block (~130 LUTs: 80 for dump logic, 50 for a dedicated UART transmitter). The raw plan called for a standalone hardware block to serialize diagnostic state over serial, triggered by a button press. Under Keel, the entire block becomes `diag.report` — a Forth word that reads every diagnostic register and writes formatted output to the inter-core mailbox. Core 1 forwards it over the existing UART. The button trigger becomes `diag.sys.btn@`, another Forth word. Zero additional RTL.

The signal mux (~30 LUTs) followed the same pattern. The raw plan included a configurable multiplexer to route internal signals to an observation point. Under Keel, this is the ILA block already specified in the parent spec — configurable via Forth words, with deeper capture than a signal mux (1K-sample circular buffer with configurable pre/post-trigger ratio), outputting through the same protocol. The trace buffer met the same fate, absorbed by the ILA's circular capture with its `TRACE:` convenience wrapper. Zero additional RTL for either.

Net savings from these three eliminations: ~160 LUTs. The diagnostic peripheral set costs ~985 LUT gross but ~825 LUT net. Section 8 of the spec accounts for this explicitly, not as an afterthought.

This is the same principle behind [composing from the constraint](../04/compose-from-the-bass.md) rather than optimizing toward it, applied at the system architecture level. The VP layer boundary — RTL is mechanism, Forth is policy — is the binding constraint. You don't write 62 registers and then figure out how to fit them into an architecture. You define the architecture and the registers fall out as consequences of what each peripheral needs to observe.

## The GDB RSP rejection

The raw plan included six `dbg.*` words for hardware debug: halt, step, resume, register read, breakpoint set, and PC observation. The spec kept two — breakpoint and PC observation — and excluded four.

The reasoning is architectural, not cost-based. Once the Forth kernel boots on Core 0, Forth *is* the debugger. You can inspect any register, call any word, peek any memory address, interactively. The VexRiscv debug module exists on Core 1 for one-time kernel bring-up via JTAG — the bootstrap path before the Forth interpreter is alive. After that, the debug module is idle overhead that you tolerate because removing it would require a second VexRiscv configuration for development versus production.

A full GDB Remote Serial Protocol implementation would have required Core 1 to speak RSP over the same UART that carries the VP protocol, multiplexing two incompatible framing conventions. It would have duplicated capabilities that Forth provides natively: halt is `SYS.RESET`, step doesn't exist because you don't step through Forth words (you call them and observe the result), register read is a memory-mapped load. The protocol complexity would have been significant. The diagnostic value would have been near zero for any failure mode where the Forth kernel is running.

The result is visible in the spec: `breakpoint_addr` and `breakpoint_armed` live in `diag.cpu`. Halt, step, resume, and register read do not. The four excluded capabilities aren't missing — they're replaced by a richer mechanism that already exists.

## The >4-state design test

The spec includes a formal test for whether a concern belongs in RTL or in firmware: "If an RTL block contains a state machine with more than four states, it is likely encoding policy. Push the policy into Core 0 firmware."

It's a heuristic, but it has a specific consequence: Core 0 acts as a compression technique. Every state machine that gets pushed from RTL into Forth saves LUTs — not just the state machine's LUTs, but the register file, output decode, and bus interface that would have been needed to configure and observe it. The Forth kernel's ~1.8-2.4K LUTs (for the rv32im VexRiscv Core 0 complex including address-range guard) amortize across every state machine they absorb.

VexRiscv itself demonstrates this principle at the CPU level. The same SpinalHDL codebase produces a Murax-class core at ~1.6-2.0K LUTs (rv32i, no caches, no debug) and a full cached configuration at ~4.5-6K LUTs (rv32im, I-cache, D-cache, debug module). You don't pay for what you don't instantiate. The plugin architecture means composability is the compression mechanism — the features are additive, not multiplicative.

The VP spec does the same thing one level up. By pushing policy out of RTL into Forth, Core 0 makes the rest of the design smaller. Two complete RISC-V cores (Core 0 + Core 1) cost ~6.3-8.4K LUTs combined — roughly 8-10% of the ECP5-85F. That's the entire orchestration and control infrastructure for the whole system. The diagnostic peripherals add 825 net LUTs on top. The mechanism pays for itself many times over through what it prevents from being synthesized as hard logic.

## What Xilinx ILA gets wrong

Compare this to the standard approach. Xilinx's Integrated Logic Analyzer is a synthesis-time insertion: you mark signals in your HDL, the tools generate capture logic, and you configure triggers through the Vivado Hardware Manager (or programmatically via Tcl, though the GUI is the common path). It works. Millions of engineers use it. And it embodies every anti-pattern the VP approach avoids.

ILA is bolted on, not architecturally integrated. Each instance is independent — it doesn't share protocol, discovery, or capture infrastructure with other debug facilities or with your application peripherals. Adding a new probe point requires resynthesis. The capture depth is fixed at synthesis time.

ILA is a tool. The VP diagnostic peripherals are *citizens*.

The practical difference shows up during iterative bring-up. With ILA, observing a new signal means: edit HDL, resynthesize (tens of minutes with open-source FPGA tools), reprogram, reconfigure triggers. With VP diagnostics, observing a new register means: define a Forth word, test it interactively, add it to the boot script. Seconds, not minutes. And the diagnostic capability you built during development is the same one that runs in the deployed system.

## Constraints as compression

The raw diagnostic plan was a shopping list. The spec is an architecture. The difference isn't organization — it's that the architecture has *constraints*, and the constraints do work.

The VP pattern constrains every peripheral to the same six-element structure. This means diagnostic peripherals share bus infrastructure, protocol framing, manifest schema, and Forth integration with every other peripheral. Shared infrastructure means shared cost. The marginal LUT cost of adding a diagnostic register to an existing VP is the register itself plus its glue logic — the bus decode, protocol extension, and Forth dictionary are incremental, not from-scratch.

The layer boundary constrains what lives in RTL versus firmware. This means the UART TX dump block can't exist as standalone RTL — it *must* be expressed as a Forth word over the existing UART, because that's what the architecture permits. The constraint didn't just suggest the better design. It required it.

The >4-state design test constrains state machine complexity in RTL. This means diagnostic state machines (watchdog timers, measurement sequencers, self-test controllers) get pushed into Forth where they're cheaper, more observable, and modifiable without resynthesis.

Each constraint eliminates a class of designs. The designs it eliminates are the ones where you'd have paid for infrastructure twice. That's compression.

The spec started with 62 items and ended with 9 peripherals, ~825 net LUTs, and three fewer hardware blocks than the naive plan. Not because someone was clever about optimization, but because the architecture's constraints made the redundant parts structurally impossible. The spec didn't describe the design and then compress it. The constraints *were* the compression. The design fell out.

That's not architecture as documentation. That's architecture as engineering.

---

🦬☀️ *[warp-core](../../research/warp-core.md) is an open-source soft GPU on ECP5-85F FPGA.
The VP architecture specs are in development; warp-core is pivoting to this framework.
[GitHub](https://github.com/modelmiser/warp-core).*
