# warp-types

Linear typestate for GPU warp divergence: compile-time prevention of
shuffle-from-inactive-lane bugs.

**Status:** v0.3.1 on crates.io

**Repository:** [github.com/modelmiser/warp-types](https://github.com/modelmiser/warp-types)

## What it is

A Rust type system that makes GPU divergence bugs into compile errors. When a
warp diverges (some lanes take one branch, others take the other), shuffles and
reductions become unsafe — reading from an inactive lane is undefined behavior.
warp-types encodes the divergence state in the type system so the compiler
rejects these bugs before they reach the GPU.

## Blog posts

- [A Fourth Point in the SIMT Divergence Design Space](../blog/posts/auto-diverge.md) — warp-core's auto-diverge model grew out of warp-types

## Links

- [crates.io/crates/warp-types](https://crates.io/crates/warp-types)
- [Concept DOI: 10.5281/zenodo.19040615](https://doi.org/10.5281/zenodo.19040615)
