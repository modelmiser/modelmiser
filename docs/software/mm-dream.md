# mm-dream

GPU-accelerated kaleidoscope screensaver built with WGSL and libcosmic.

**Repository:** [github.com/modelmiser/mm-dream](https://github.com/modelmiser/mm-dream)

## What it is

A real-time fragment shader that generates kaleidoscopic patterns through
rotozoom transformations with configurable fold symmetry. Runs as a COSMIC
desktop application on Wayland via libcosmic's wgpu shader widget.

Features:

- Analytical fold symmetry (2, 5, and 10-fold) with radial mirroring
- Zoom state machine with smoothstep-eased transitions
- CRT post-processing (barrel distortion, scanlines, phosphor grille, vignette)
- Auto-cycling through pattern combinations
