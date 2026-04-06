---
date: 2026-03-17 09:00:00
categories:
  - warp-types
---

# What the Type Erases To

A type system that compiles to nothing is not overhead you tolerate — it is proof the compiler can verify and then discard.

<!-- more -->

## The bug class

GPUs execute programs in warps — groups of 32 threads running in lockstep. When threads take different branches, some lanes become inactive. The inactive lanes still exist physically — their registers hold whatever was there before — but they are not participating in the current control path.

A shuffle is a warp-level data exchange: lane *i* reads a value from lane *j*. If lane *j* is inactive, the read returns whatever is in that register. Not zero. Not an error. Whatever was there. This is undefined behavior in the PTX ISA, and it manifests as silent data corruption.

This is not a theoretical concern. NVIDIA's own `cuda-samples` had it: issue #398, in `reduce7`, their official parallel reduction sample. When `blockDim.x == 32`, the ballot narrows to a single lane, and `shfl_down_sync` reads from lanes that didn't participate. The sum comes back wrong. No crash, no warning — a quietly incorrect number propagated to the output. PIConGPU, a plasma physics simulation, had undefined behavior in its warp communication that went undetected on K80 GPUs for months (issue #2514). Pre-Volta hardware masked the bug through implicit lockstep — no wrong output was observed, and the fix was preventive.

NVIDIA's fix for this was `__shfl_sync(mask, ...)` — pass an explicit mask of participating lanes. But `__activemask()` returns the hardware execution mask, which encodes the wrong information. The mask can be "correct" — matching the hardware state — and still wrong, because the code shouldn't be shuffling in that divergence state at all. The mask tells you what IS active. It doesn't tell you what SHOULD be active. The distinction is the entire bug class.

## Three paths

**Path 1: Unchecked divergence.** CUDA's approach. You can shuffle whenever you want. Pass a mask. Get it right or get silent corruption. This is what shipped in every CUDA toolkit from 9.0 onward.

**Path 2: No divergence.** The Hazy megakernel approach (Stanford, 2025) takes the opposite position: maintain warp-uniform execution at all times — all lanes always active. Safe, and effective for persistent-thread workloads like LLM inference. But it restricts algorithms that naturally have data-dependent control flow.

**Path 3: Typed divergence.** `Warp<S>` is a zero-sized phantom type parameterized by an active-set marker. The type tells you which lanes are live. Shuffle is only defined on `Warp<All>`. Diverge consumes the parent and produces two sub-warps. Merge requires both halves.

```rust
let warp: Warp<All> = Warp::kernel_entry();
let data = PerLane::new(1i32);

// Full warp: shuffle works
let _sum = warp.reduce_sum(data);

// Diverge: parent consumed, two children produced
let (evens, odds) = warp.diverge_even_odd();

// evens.shuffle_xor(data, 1);
// ^^^^^ COMPILE ERROR: no method `shuffle_xor` on Warp<Even>

// Merge requires BOTH halves — can't forget one
let restored: Warp<All> = merge(evens, odds);
let _sum = restored.reduce_sum(data); // works again
```

The method doesn't exist on partial warps. Not "exists but panics." Not "exists but returns an error." The trait implementation is not present. `rustc` rejects it the same way it would reject calling `.sin()` on a `String`.

The parent warp is gone after diverge — Rust's ownership system moves it. You cannot use it again. This is the exact property that CUDA's mask-passing cannot enforce: the old handle is still syntactically valid in CUDA, so you can shuffle on it. In the type system, the old handle is a moved value. The compiler error is "use of moved value: `warp`."

## The claim

Most phantom type libraries claim "zero overhead" because `PhantomData` is zero-sized. This is necessary but not sufficient. The compiler might generate different code paths, keep type-related metadata, or fail to optimize through trait boundaries. The interesting question is whether the optimized machine code is identical with and without the type system.

The evidence chain has two stages.

## Stage 1: LLVM IR

Two functions with `#[inline(never)]` and `#[export_name]` to prevent the optimizer from hiding them:

`warp_types_zero_overhead_butterfly` creates a `Warp<All>`, runs 5 `shuffle_xor` permutations through the phantom type, then calls `reduce_sum` (which internally does 5 more shuffle-XOR steps plus additions). Ten shuffles total, all gated by the `Warp<All>` type.

Compiled with `--release --emit=llvm-ir`, the function body is:

```text
%1 = shl i32 %data, 5
ret i32 %1
```

Two instructions. The butterfly with identity shuffles on a CPU target collapses to multiplication by 32 (left-shift by 5). The optimizer saw through every trait bound, every `PhantomData` construction, every method dispatch on `Warp<All>`, and reduced ten operations to one shift. No `Warp`, no `PhantomData`, no active-set symbols appear in the optimized IR.

`warp_types_zero_overhead_diverge_merge` creates a `Warp<All>`, diverges to even/odd, merges back, and returns data unchanged. The optimized IR:

```text
ret i32 %data
```

A no-op. The diverge-merge round trip — the core mechanism of the type system — generates zero instructions. The warp handles were created, consumed, split, and reassembled entirely within the type system. LLVM saw nothing worth keeping.

The only `Warp`-containing symbols in the entire optimized `.ll` file are error message strings (for `Debug` formatting in test code) and `DynWarp` functions that intentionally carry runtime state. Everything in the static type system is erased completely.

## Stage 2: PTX

LLVM IR proves erasure survives Rust-to-LLVM compilation. But GPU kernels target PTX, not x86. The second stage compiles typed and untyped butterfly reductions to actual GPU assembly via `nvptx64-nvidia-cuda`.

Two CUDA functions compiled to PTX with `nvcc -ptx -arch=sm_89 -O2`:

```c
__device__ __noinline__
int butterfly_untyped(int data) {
    data += __shfl_xor_sync(0xFFFFFFFF, data, 16);
    data += __shfl_xor_sync(0xFFFFFFFF, data, 8);
    data += __shfl_xor_sync(0xFFFFFFFF, data, 4);
    data += __shfl_xor_sync(0xFFFFFFFF, data, 2);
    data += __shfl_xor_sync(0xFFFFFFFF, data, 1);
    return data;
}
```

And the typed version — same operations, with `Warp<All>` phantom state tracking each step. The `__noinline__` attribute is load-bearing: without it, the compiler inlines both into their callers, and there are no distinct function bodies left to compare.

After extracting the `.func` blocks and normalizing mangled names:

```text
IDENTICAL PTX
```

Both functions emit 5x `shfl.sync.bfly.b32` + 5x `add.s32`, same registers, same instruction ordering. The type annotations produce zero additional PTX instructions, zero additional registers, zero additional bytes.

## Stage 3: Real GPU hardware

4 typed kernels compiled to PTX, validated by `ptxas` for `sm_90`, and executed on an NVIDIA H200 SXM (Hopper architecture):

| Kernel | Expected | Got | Status |
|--------|----------|-----|--------|
| butterfly_reduce | 32 | 32 | PASS |
| diverge_merge_reduce | 496 | 496 | PASS |
| reduce_n | 32 | 32 | PASS |
| bitonic_sort_i32 | sorted | sorted | PASS |

The same kernels pass on RTX 4000 Ada (sm_89). The diverge_merge_reduce test is the interesting one: it diverges a warp, merges it, then reduces — exercising the full typestate lifecycle on actual GPU silicon. The result (496 = sum of 0..31) would be wrong if the diverge or merge introduced any runtime state.

## The killer demo

The `demo.sh` script runs three beats. First, the CUDA `reduce7` bug pattern: sum of 32 ones through `shfl_down_sync` with a partial mask. Expected: 32. Got: 1. Lane 0 reads from lane 16, which didn't participate. The register holds whatever initialization value was there — in this case, the data from lane 16's load, which happens to be 1. Silent, deterministic, wrong.

Second, an analogous pattern attempted in the type system. `Warp<All>` diverges into `Warp<Even>` and `Warp<Odd>`. Attempting to shuffle on the partial warp is rejected:

```text
error[E0599]: no method named `shuffle_xor` found for `Warp<Even>`
```

Third, the typed fix. All lanes load data (inactive lanes contribute 0). `Warp<All>` shuffles with full participation. Same GPU, same algorithm. Sum: 32. Correct.

The buggy pattern is not detected at runtime. It does not exist in the type system.

## The gradual bridge

Not everyone can annotate all their code with phantom types immediately. A real codebase has thousands of lines of existing CUDA, and "rewrite everything" is not a migration strategy.

`DynWarp` is the bridge. It carries its active mask at runtime — two `u64` fields (16 bytes) for the active mask and the full-warp mask. Every operation that would be a type error on `Warp<S>` becomes a `Result::Err` on `DynWarp`. You can shuffle on a `DynWarp` and get a runtime check instead of a compile-time rejection.

The migration path is three phases. Start with `DynWarp::all()` — drop-in replacement with runtime checks for everything. At function boundaries, call `ascribe::<All>()` to validate the mask and get a `Warp<All>` back. Progressively replace `DynWarp` with `Warp<S>` as confidence grows.

```rust
// Phase 1: all dynamic
let dyn_warp = DynWarp::all();
let (evens, odds) = dyn_warp.diverge(Even::MASK);
assert!(evens.shuffle_xor_scalar(42, 1).is_err()); // caught at runtime

// Phase 2: ascribe at boundary
let merged = evens.merge(odds).unwrap();
let warp: Warp<All> = merged.ascribe::<All>().unwrap();

// Phase 3: fully typed — DynWarp gone
let _sum = warp.reduce_sum(data);
```

This is Siek & Taha's gradual typing (2006) specialized for warp active sets. The "cast" is `ascribe()` — it checks the runtime mask against the static type's expected mask and either returns the typed handle or an error.

The incentive structure is self-reinforcing: `DynWarp` costs 16 bytes and a branch per operation. `Warp<S>` costs zero bytes and zero branches. You get both safety and performance by adding types. Migration isn't a tax you pay for correctness — it's an optimization the type system rewards.

## What erasure means

"Zero overhead" is not a claim about the source representation. It is a claim about the generated machine code.

`PhantomData` being zero-sized is the mechanism. The evidence is what comes out the other end: LLVM IR where `shl i32 %data, 5` is all that remains of ten shuffle operations through phantom state. PTX where typed and untyped butterflies produce byte-identical instruction sequences. GPU hardware where diverge-merge round trips return correct sums because nothing was added to get wrong.

A type system that erases to nothing is proof. The annotations carry enough information for the compiler to verify safety properties — shuffle only with all lanes active, no use after diverge, merge requires both halves — and then discard every trace of that verification from the output. The program that runs is the program you would have written without the type system, minus the bugs.

395 tests. Two compilation stages. Four GPU kernels on real hardware. One type system that isn't there when you go looking for it in the binary.

---

🦬☀️ *warp-types is a zero-overhead type system for GPU warp divergence safety. v0.3.1 on [crates.io](https://crates.io/crates/warp-types). [GitHub](https://github.com/modelmiser/warp-types).*
