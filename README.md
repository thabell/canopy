# canopy

🇷🇺 [Читать на русском](README.ru.md)

> **One script tag. Zero asset files. Infinite terrain.**  
> Procedural 3D landscape as a living webpage background — mountains, forests, lakes, full day/night cycle — all generated on the GPU from math, no image textures required.

---

## Live deployment

`canopy` — the hero background animation of **[Krona](https://krona-edu.tilda.ws/)** — an online EGE/OGE prep school. Krona is individual work instead of group webinars, only certified EGE experts, full unabridged course material with designer presentations, flashcards, written assignment review, and progress analytics. Stack: Django + Wagtail, custom Figma plugins, ML-based task classification, own VPS. The landscape runs as a Tilda block with no performance complaints.

---

## Technical architecture

Procedural real-time 3D landscape running on Three.js — moves endlessly, generates mountains/water/forests from Perlin noise directly on the GPU. 10 tree types with unique crown geometry via Worley noise, instancing (2 draw calls instead of 20), adaptive quality based on the user’s hardware. Day cycle, wind, fog. Embeds into any site with a single script as a living background. No image files, no asset pipeline, no build step.

### Five independent noise layers

Terrain height is the sum of five separate FBM (Fractal Brownian Motion) passes, each with its own frequency, amplitude, octave count, lacunarity, and roughness:

| Layer | Role | Key params |
|---|---|---|
| `BASE` | Ground micro-detail | f=0.019, A=7, oct=5 |
| `HILL` | Rolling hills | f=0.013, A=14, oct=6 |
| `MTN` | Mountain ridges via ridge mask | f=0.0062, A=48, oct=8 |
| `LAKE` | Lake basin placement | f=0.006, threshold-based |
| `FOREST` | Forest coverage mask | f=0.008, threshold-based |

`MTN` uses a smoothstep ridge mask before multiplying — sharp peaks without spiky artifacts. `LAKE` depresses terrain below a configurable depth when FBM crosses a threshold. All five layers live inside the GLSL vertex shader; the CPU never touches height values during rendering.

### GPU-side terrain

Geometry is a flat `PlaneGeometry`. The vertex shader evaluates the full 5-layer noise stack per vertex and displaces `y` in place. Three chunks recycle as the camera moves — no new geometry allocation per frame.

### Crown shape: Worley + Perlin FBM

Each tree crown is an icosphere deformed in the vertex shader by a **3D Worley noise + 3D Perlin FBM** blend:

- `crownFreq` — cell size (lower = bigger blobs)
- `crownNoise` — displacement depth
- `lumpMix` — 0 = sharp Worley cells, 1 = smooth FBM surface
- `blobSpreadX/Y` — post-noise geometry stretch (real horizontal/vertical scaling)
- `blobYBias` — shifts the noise sampling center vertically (drooping vs raised crown)

Four archetypes (`round`, `spreading`, `columnar`, `oval`) provide a base envelope on top of which blobs are extruded.

### Wind

Three-level model, no dedicated gust logic needed.

**Level 1 — global wind vector (CPU, per-frame):**

```
windVec.x = (sin(t·0.40)·0.60 + sin(t·1.10)·0.25) × strength
windVec.z = (cos(t·0.35)·0.50 + cos(t·0.90)·0.20) × strength
windVec.y =  sin(t·0.30)·0.08 × strength
```

Each horizontal axis sums **two sine waves with non-integer frequency ratios** (0.40:1.10 ≈ 2.75, 0.35:0.90 ≈ 2.57). When both components are in phase they reinforce — a gust. When out of phase they partially cancel — a lull. Irregular gusts emerge without any explicit gust logic. The `x` axis uses `sin`, `z` uses `cos` — 90° offset — so wind direction slowly rotates rather than pushing back and forth along one axis.

**Level 2 — spatial phase per tree (vertex shader):**

Each tree's sway is offset by `pos_x · 0.10 + pos_z · 0.15`, so a gust travels across the forest as a visible wave rather than hitting all trees simultaneously.

**Level 3 — per-crown irregularity (vertex shader):**

```glsl
float sw = sin(lp)·0.70 + sin(lp·2.3 + 0.8)·0.30;
```

Another pair of non-integer-ratio components applied per vertex — each crown gets its own irregular flutter independent of the global wind.

### Leaf texture — no PNG

The fragment shader generates per-species leaf patterns using 2D Voronoi + FBM combinations:
- `round` → Voronoi cells + smooth FBM
- `lobed` → distorted Voronoi + angular sin term
- `pinnate` → stretched UV space + horizontal stripe modulation
- `serrated` → high-frequency double-layer Voronoi

Fragments below a density threshold call `discard` — transparent leaf gaps with no alpha texture.

### Single-material instancing (2 draw calls for 10 species)

All 10 species share **one `ShaderMaterial`**. Species parameters are packed into four `InstancedBufferAttribute` vec4s per instance:

```
aP0: rgb=leaf color,   w=crownType (0-3)
aP1: blobSpreadX/Y, yBias, crownNoise
aP2: crownFreq, lumpMix, leafShape, leafDensity
aP3: edgeSharpness, leafScale, detailRough, leafAspect
```

16 floats per tree. No uniform switching, no material rebinding. Two patch meshes → **2 draw calls for all forest geometry**, regardless of species mix.

### GPU heightmap readback for tree placement

Tree placement runs on the CPU (grid walk + noise thresholds). Problem: height at any world point is defined in GLSL, not JS. Solution: render a fullscreen quad with the same GLSL height function into a `WebGLRenderTarget`, `readRenderTargetPixels` into a `Float32Array`, bilinearly sample it per candidate tree. One GPU bake per chunk recycle — no JS reimplementation of the noise stack.

### Adaptive quality pipeline

1. **Probe phase** — first 15 frames skipped (driver warmup), next 60 frames measured at minimal settings
2. **Preset selection** — FPS mapped to one of 6 presets: `ultralow → low → medium → high → ultra → extreme`
3. **Runtime adaptive** — if smoothed FPS drops below `preset.minFPS` for 2 consecutive 7-second windows, auto-downgrade one level

Switching presets: vertex attributes on patch geometries are hot-swapped by reference to either `IcosahedronGeometry(1,3)` (642 verts) or `IcosahedronGeometry(0.88,1)` (42 verts) — no geometry rebuild, no buffer reallocation.

---

## Species system

10 deciduous species with ecologically plausible elevation ranges and density weights:

`Quercus` · `Tilia` · `Fagus` · `Fraxinus` · `Ulmus` · `Carpinus` · `Alnus` · `Juglans` · `Corylus` · `Castanea`

Each carries 13 visual parameters. Mixed forest emerges naturally from elevation filtering + density FBM + seeded per-cell RNG — no hand-placed objects. Parameters live in `species-config.js` and are edited via `crown-tuner.html`.

---

## Repository structure

```
canopy/
├── landscape 2.0.html      ← current (Worley crowns, instanced attrs, adaptive quality)
├── landscape 1.0.html      ← first version (sphere crowns, instanceColor, simpler pipeline)
├── crown-tuner.html        ← interactive species editor: orbit view, live sliders, export/import
├── blender_node_export.py  ← Blender script: exports material/GeoNodes node trees to JSON
├── species-config.js       ← current tuned species params (paste into tuner or landscape)
├── README.md
└── README.ru.md
```

**`crown-tuner.html`** — standalone Three.js app. All 10 species side-by-side with orbit camera. Live sliders for every crown and leaf parameter, export to JSON / copy as JS. Accepts pasted configs for A/B comparison.

**`blender_node_export.py`** — run inside Blender's scripting panel. Exports node names, types, socket values, and links from any material or GeometryNodes modifier to `/tmp/nodes_export.json`. Used during terrain/noise prototyping to transfer Blender shader graphs to GLSL. Thanks for the project and inspiration, [qiri](https://youtu.be/E0tr9SMxvH0)!

**`landscape 1.0.html`** — first version. Uses `instanceColor` for species color, simpler `SphereGeometry(1,8,5)` crowns without per-instance shape parameters, JS-side heightmap sampling, fixed `trees` count per preset.

---

## Usage

Three.js r128 is bundled inside the script block. Drop `landscape 2.0.html` (or embed the `<div class="landscape">` block with its `<script>`) into any page. Set `C.DEBUG = true` to enable the live control panel (presets, biome colors, wind, tree density, species weights, zone editor).
Two patch meshes are used for performance optimization. If you want trees to fade in from the fog instead of popping in, find the `TREE_CHUNKS` constant and change its value from 2 → 3.

---

## Performance

| Preset | Terrain tris | Crown verts | Tested on |
|---|---|---|---|
| ultralow | ~1.5k | 42v × N | old mobile / weak integrated |
| low | ~4k | 42v × N | integrated GPU |
| medium | ~9.6k | 42v × N | mid laptop |
| high | ~26k | 42v × N | iPhone 11 |
| ultra | ~60k | 642v × N | Windows laptop |
| extreme | ~90k | 642v × N | Mac (large headroom) |

Draw calls per frame: **5–6** (sky + 3 terrain chunks + 2 tree patches).

---

## Perspectives

- Season system: autumn/spring color shifts via uniform lerp, no geometry changes needed
- Water surface: a flat plane at `WATER_LEVEL` with a wave shader — one draw call away
- Conifers and any new species: the Worley crown system already handles any shape — adding a species is one config object + ~10 min in `crown-tuner.html`, no code changes, zero performance cost regardless of how many species exist (GPU sees one instance stream, not N species)
- Audio: spatial wind and ambient sound can tie directly to the existing wind uniform
- The adaptive pipeline and species config format drop into any Three.js project as-is

---

## Dependencies

- [Three.js r128](https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js)
- Nothing else.
