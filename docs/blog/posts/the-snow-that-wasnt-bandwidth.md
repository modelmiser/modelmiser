---
date: 2026-04-13 18:00:00
categories:
  - warp-core
---

# The Snow That Wasn't Bandwidth

When the obvious diagnosis is wrong, the real bug is always simpler.

<!-- more -->

## The symptom

Mandelbrot rendering on warp-core. Four SIMT pipelines computing escape-time iterations, writing pixels to a shared SDRAM framebuffer, scanline prefetch feeding the HDMI encoder. The image should take about 3 seconds to converge — 76,800 pixels across a 320x240 framebuffer, deep zoom near the boundary.

What appears on screen: snow. Not a black screen, not a corrupted image — scattered pixels, some correct, some wrong, shifting between frames. The kind of visual noise you get when two processes are fighting over a shared resource.

The obvious diagnosis writes itself. Four warps are issuing SDRAM writes. The scanline prefetch is issuing SDRAM reads. The write drain from the framebuffer FIFO is issuing more SDRAM writes. All of this through one 16-bit SDRAM bus at 33 MHz. Classic bandwidth starvation — too many consumers, not enough bus cycles, reads and writes stepping on each other. The snow is pixels that lost the arbitration race.

I spent a day on this theory. Adjusted round-robin priorities. Measured FIFO fill levels. Calculated bandwidth budgets: 33 MHz × 16 bits = 66 MB/s theoretical, minus refresh overhead, minus CAS latency, minus turnaround penalties. The numbers were tight but should have worked. The snow persisted.

The diagnosis was wrong.

## The race

The framebuffer is double-buffered. `buf_select` is a 1-bit register in the pixel clock domain that toggles at vsync — every 16.7ms, the display flips which buffer it reads from, and the renderer is supposed to be writing to the other one. Standard double-buffering. Every GPU since the VGA era does this.

The problem is *when* `buf_select` gets sampled.

Pixels enter the framebuffer write path through an async FIFO — warp clock domain to SDRAM clock domain. A pixel is enqueued with its framebuffer address, which includes the buffer bit. On the drain side, `fb_writer` computes the SDRAM address:

```verilog
wire wr_buf = ~buf_select_sdram;  // write to the non-display buffer
wire [17:0] wr_addr = {wr_buf, pixel_y[7:0], pixel_x[8:0]};
```

The address is computed at *drain* time, not *enqueue* time. The FIFO holds the pixel coordinates and color. The buffer selection happens when the FIFO entry reaches the head and the SDRAM port is ready. Between enqueue and drain, `buf_select` can toggle.

During a 3-second Mandelbrot render, vsync fires 180 times. Each toggle flips `buf_select`, which flips `wr_buf`, which redirects all subsequent FIFO drains to the opposite buffer. A pixel enqueued during frame N might drain during frame N+3. The buffer it lands in depends on the parity of the vsync count at the moment the SDRAM port happens to be free — a timing relationship that depends on SDRAM refresh cycles, read/write turnaround, and the phase relationship between two asynchronous clocks.

The result: pixels scatter across both buffers. Neither buffer ever holds the complete image. The display shows whichever buffer `buf_select` currently points to, which contains roughly half the pixels — the half that happened to drain during the right parity. The other half is in the other buffer, invisible. Next vsync, the buffers swap, and you see a different half. Snow.

This is not a bandwidth problem. The SDRAM bus is delivering every pixel. Every write completes. No data is lost. The pixels just land in the wrong buffer.

## What every GPU gets right

Double-buffering has been a solved problem since the late 1980s. The principle is universal: the buffer swap is synchronized to the vertical blanking interval, and during rendering, the swap is *inhibited*. You write to buffer B while the display scans buffer A. When the frame is complete, you signal readiness. At the next vsync — and only at vsync — the hardware swaps. Until you signal, it doesn't.

Vulkan calls this a swap chain. You acquire an image, render to it, present it. The presentation engine controls when the swap actually happens. DirectX has the same model. Even the original VGA page-flipping worked this way — you wrote the start address register during vblank, and it took effect at the next vertical retrace. The swap is always gated.

Warp-core's `buf_select` toggled freely at every vsync, regardless of whether the renderer had finished. For single-frame rendering — fill the framebuffer once and stop — this works fine. The fill completes within one frame period, and by the time `buf_select` toggles, all pixels are in the correct buffer. The bug only appears during multi-frame renders, where the write stream spans many vsync intervals.

This is what you miss when you build custom hardware without the abstraction layers that normally handle it. A GPU driver manages the swap chain. A display server manages the page flip. When you're writing raw Verilog, those layers don't exist, and it's on you to implement the invariant they encode: *the swap is gated on frame completion*.

## The fix: one bit of state

```verilog
// MMIO register: firmware writes 1 to inhibit, 0 to release
reg swap_inhibit_warp;  // warp clock domain
reg swap_inhibit_sync1, swap_inhibit_sync2;  // CDC to pixel clock

always @(posedge pixel_clk) begin
    swap_inhibit_sync1 <= swap_inhibit_warp;
    swap_inhibit_sync2 <= swap_inhibit_sync1;
end

always @(posedge pixel_clk) begin
    if (vsync_edge && !swap_inhibit_sync2)
        buf_select <= ~buf_select;
end
```

The firmware side is two instructions:

```asm
    LI r1, 1
    CSR_WR r1, SWAP_INHIBIT   ; freeze buffer swap
    ; ... render Mandelbrot (3 seconds) ...
    LI r1, 0
    CSR_WR r1, SWAP_INHIBIT   ; release — swap at next vsync
```

One MMIO register. One bit, CDC'd through a 2-flip-flop synchronizer to the pixel clock domain. Two firmware instructions — one before the render, one after. The snow disappears. Both buffers hold complete, correct images from that point forward.

The 180 vsync toggles during a 3-second render collapse to zero toggles while `swap_inhibit` is asserted. The buffer selection becomes deterministic: every pixel drains to the same buffer, because the buffer doesn't change until the firmware says the frame is done.

## The second bug in the same path

With the buffer race fixed, a different artifact appeared: a partial scanline of snow — roughly a third to two-thirds of one horizontal line — that tracked the current prefetch position. The Mandelbrot image was correct everywhere except this narrow band where the display prefetch was actively reading.

This one actually *was* a bandwidth problem — but a specific, structural one. The scanline prefetch and the framebuffer write drain shared an FSM in `scanline_buf.v`. They were time-multiplexed: the prefetch would read a scanline, then the write drain would flush pending writes, then the prefetch would read the next scanline. They couldn't run concurrently because they shared the FSM's state register.

The fix was architectural: extract `fb_writer.v` as a dedicated module with its own FSM. Prefetch reads through SDRAM port 0. Framebuffer writes through port 1 (or through the round-robin arbiter when port 1 isn't available). The two paths now run concurrently instead of taking turns.

But even with concurrent operation, the partial-scanline artifact persisted during SDRAM contention — when a warp store burst and a scanline prefetch compete for the same port, the prefetch can stall long enough to miss its deadline, and the display reads stale data from the scanline buffer.

The final piece: back-pressure. CDC-synchronize `prefetch_pending` into the warp clock domain as a `freeze` signal. When the display is prefetching, warps stall. The display always wins SDRAM port 0.

```verilog
// In warp clock domain
reg freeze_sync1, freeze_sync2;
always @(posedge warp_clk) begin
    freeze_sync1 <= prefetch_pending;
    freeze_sync2 <= freeze_sync1;
end
wire warp_freeze = freeze_sync2;
```

Cost: ~12% throughput penalty. The warps lose roughly one in eight cycles to prefetch stalls. A 3-second Mandelbrot render becomes 3.4 seconds.

## Check layer N-1 first

The dominant engineering rule in this project, stated repeatedly in the devlog: **check layer N-1 before trying harder at layer N**.

The snow looked like SDRAM bandwidth starvation — a layer-N resource problem. The fix was a 1-bit control register at layer N-1, the buffer management plane. The FSM sharing was another layer N-1 issue: it looked like the SDRAM couldn't keep up with concurrent reads and writes (layer N), but the real problem was that the reads and writes weren't concurrent at all because they shared a state machine (layer N-1).

Only the prefetch back-pressure fix was a genuine layer-N solution — yielding bandwidth to the display. And even that fix only became *necessary* after the two layer N-1 bugs were resolved. Before the buffer race fix, the back-pressure would have reduced snow density without eliminating it, because the fundamental problem wasn't bandwidth contention but pixels landing in the wrong buffer. You can't fix a routing problem by adding capacity.

The diagnostic sequence matters: fix the control plane first, then measure whether you actually have a resource problem. In this case, fixing `swap_inhibit` eliminated 95% of the snow. Extracting `fb_writer.v` eliminated the horizontal band. The freeze mechanism cleaned up the remaining edge cases. Three bugs that all looked like the same symptom — snow — with three different root causes at two different architectural layers.

The temptation after seeing snow on a shared-bus system is to start optimizing bandwidth. More efficient SDRAM scheduling. Wider burst transfers. Priority-based arbitration. All of that work would have been wasted, because the bus was delivering every byte correctly. The pixels were just going to the wrong address.

One bit of state. Two firmware instructions. That's what 180 vsync toggles worth of scattered pixels came down to.

---

🦬☀️ *[warp-core](../../research/warp-core.md) is an open-source soft GPU on ECP5-85F FPGA. [GitHub](https://github.com/modelmiser/warp-core).*
