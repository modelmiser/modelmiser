---
date: 2026-03-19
categories:
  - mm-dream
---

# Why the Kaleidoscope Looks Symmetric When It Isn't

A fragment shader, a CRT filter, and the scale gap between mathematics and perception.

<!-- more -->

## A kaleidoscope that breaks its own symmetry

mm-dream is a GPU-accelerated kaleidoscope. A WGSL fragment shader folds
the screen plane into a D_N fundamental domain — 2-fold, 5-fold, or 10-fold
symmetry with radial mirroring — then paints raster bars, rotozoom
transformations, and procedural textures onto the folded coordinates.
Everything that happens before the fold is automatically symmetric, because
every pixel maps through `fold_coords` before anything is drawn.

Then CRT post-processing ruins it.

Scanlines at ~2 pixel pitch. A phosphor grille at ~3 pixel pitch. Barrel
distortion curving the edges. Vignette darkening the corners. All of these
are screen-space effects — they operate on the output image, not on the
folded coordinates. And the fold angle rotates at irrational rates relative
to the screen axes. No element of D_N generically aligns a horizontal
scanline with its rotated counterpart.

The mathematical symmetry group drops from D_N × Z₂ to {e} — the trivial
group. No symmetry at all.

And yet the mandala looks perfectly symmetric.

## The scale gap

The resolution is spatial frequency. The fold structure operates at ~5-10
cycles per screen width. The CRT effects operate at ~500 cycles per screen
width. There are two orders of magnitude between them.

Human symmetry detection — the processing that happens in V1, V2, and V4
of the visual cortex — doesn't work on raw pixel data. It works on smoothed,
multi-scale representations. Features at the scale of individual scanlines
are below the resolution at which the symmetry detectors operate. The visual
system evaluates a version of the image where CRT perturbations have already
been averaged away.

This isn't an approximation error. It's a fundamental property of how
scale-space analysis interacts with symmetry groups.

## Making it formal

Define G_σ(f) as the set of symmetries that survive Gaussian smoothing at
scale σ:

G_σ(f) = { g ∈ O(2) : ‖W_σ(f∘g) - W_σ(f)‖₂ < ε · ‖W_σ(f)‖₂ }

where W_σ is a Gaussian kernel at scale σ. At σ = 0 (no smoothing), you
see the raw pixels: G₀ = {e}. The CRT broke everything.

As σ increases past ~3 pixels — the CRT feature scale — the scanlines and
grille vanish into the blur. The fold symmetry re-emerges:
G_σ ≈ D_N × Z₂.

Increase σ further past the bar length scale (~50-100 pixels), and even
the bar structure dissolves. The image approaches radial uniformity:
G_σ → O(2) × Z₂.

This is a **filtration** on the symmetry group:

```text
{e}  ⊂  D_N × Z₂  ⊂  O(2) × Z₂
 ↑         ↑              ↑
σ = 0    σ ≈ 3px       σ ≈ 100px
```

Each inclusion activates at a critical scale where a class of
symmetry-breaking features drops below the smoothing resolution. The
"distance" between the mathematical group ({e}) and the perceptual group
(D_N × Z₂) isn't a measure of approximation quality — it's σ_c itself,
the critical scale.

## What the GPU forced

This analysis wasn't planned. It fell out of a debugging question: "why does
the CRT filter not visibly break the symmetry?"

The fragment shader architecture is what made the question precise. Every
pixel is computed independently from coordinates and time — no frame
accumulation, no state. The fold operation is an exact mathematical
projection. The CRT effects are exact per-pixel functions. There's no
blur, no anti-aliasing, no ambiguity about what the shader produces.
The output is mathematically {e}-symmetric and perceptually D_N-symmetric,
and the gap between those two facts demands an explanation.

On a traditional CPU renderer with accumulated state, anti-aliased
compositing, and resolution-dependent blur, the question wouldn't arise
as cleanly. The shader's analytical precision is what makes the symmetry
gap legible.

## The pattern generalizes

The scale-dependent symmetry gap isn't specific to kaleidoscopes or CRT
filters. It appears anywhere symmetry-breaking perturbations are
scale-separated from symmetric structure:

**Tiled floors.** A tiled bathroom floor has exact translational symmetry
in its geometry — but the grout lines, slight color variations, and
lighting gradients break it. Step back and squint (increase σ) and the
symmetry returns. The mathematical group of the floor-with-imperfections
is {e}; the perceptual group is the wallpaper group of the tile pattern.

**Crystal structures.** A real crystal has thermal vibrations that
instantaneously break all lattice symmetry. But X-ray diffraction (which
effectively averages over time and space — a physical Gaussian kernel)
recovers the space group. Crystallographers don't say "the crystal has no
symmetry" — they say "the symmetry is at a different scale."

**Music.** A melody has pitch symmetries (transposition, inversion) that
are broken by performance variation — timing fluctuations, dynamic accents,
timbral differences. The listener perceives the symmetry because pitch
processing operates on a representation where performance noise has been
smoothed.

In each case, the mathematical symmetry group of the raw signal is trivial
or nearly so. The perceptual symmetry group is rich and structured. The
gap between them is fully explained by scale-space filtration — no appeal
to "approximate symmetry" or "symmetry tolerance" is needed.

## The torus underneath

One more structural observation from the shader. The fold operation has two
independent periodicities: the angular fold (N sectors) and the radial
mirror. The phase space of two independent periodicities is a torus — T².
This wasn't a design choice. The `fold_coords` function maps (r, θ) to a
folded (r', θ'), and the topology of that map is toroidal whether or not
you render it as a torus.

You could render this as an actual torus mesh — map the folded output onto
the surface and watch the kaleidoscope wrap around it. But the topology is
already there in the 2D shader, hidden in the periodicity structure of
`fold_coords`, waiting to be noticed.

This is the recurring theme: the GPU's constraints — stateless computation,
analytical precision, per-pixel independence — don't limit what you can
express. They force you to understand the mathematics of what you're
expressing. And sometimes the mathematics reveals structure you didn't know
was there.

---

🦬☀️ *[mm-dream](../../software/mm-dream.md) is a GPU-accelerated kaleidoscope
screensaver built with WGSL and libcosmic.
[GitHub](https://github.com/modelmiser/mm-dream).*
