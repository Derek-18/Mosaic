# Designing a Manufacturable Tesserae Mosaic Generator with Assembly Instructions and Realistic Rendering

## Executive Summary
A production-grade photo-to-mosaic system is feasible when treated as three coupled systems:
1. **Computational design**: convert images into discrete tessera geometry, color/material, and orientation under hard constraints.
2. **Fabrication documentation**: emit clear, buildable instructions (maps, numbering, BOM, cut sheets, sequencing).
3. **Physically based rendering (PBR)**: preview true material behavior (glass/smalti/metallic/grout) under realistic lighting and view.

The central risk is not stylization quality, but **design-to-fabrication closure** (mixed shapes, variable thickness, grout limits, and optional tile pitch/tilt). Start with a constrained beginner mode and progressively unlock expert features.

---

## Product Scope

### Functional Requirements
- **FR1 Input & calibration**: ingest raster images and optional vector guides; define physical size, viewing distance, and install context.
- **FR2 Manufacturable tessera plan**: generate non-overlapping tessera polygons with grout clearance and bounded tolerances.
- **FR3 Material-aware matching**: assign palette/material and optional orientation (yaw/pitch/tilt) to minimize visual error.
- **FR4 Fabrication outputs**: produce assembly templates, numbering, BOM, cut diagrams, and method-specific guides (direct/indirect).
- **FR5 Realistic preview**: provide real-time PBR preview and offline high-fidelity render.
- **FR6 Interoperability**: export SVG/PDF/DXF for 2D workflows and glTF/USDZ for 3D/AR.

### Non-Functional Requirements
- Deterministic/reproducible outputs (input + seed => same project).
- Progressive performance (quick first pass + refinements).
- Full traceability (why each tessera choice was made).

---

## Parameterization and Constraint Model

Minimum user controls:
- Mosaic dimensions + boundary shape.
- Color count and palette strategy (fixed/inventory/hybrid/region-specific).
- Tile shape set (grid/hex/tri/irregular) and size distribution.
- Grout color and width bounds.
- Per-material PBR attributes (roughness/specular/metallic/transmission/IOR).
- Orientation controls (yaw and optional pitch/tilt bounds/step size).
- Substrate and adhesive settings.
- Budget and waste factors.
- Cutting feasibility constraints (min edge length, min angle, tool assumptions).

Every tessera should encode:
- 2D polygon footprint.
- Thickness class and material family.
- Grout clearance envelope.
- Pose (x, y, yaw, optional pitch/tilt).
- Constraint metadata (wet-area compatibility, mortar requirements, tolerance class).

---

## Image-to-Tessera Pipeline

1. **Edge-preserving preprocessing**
   - bilateral/domain-transform smoothing to reduce noise while preserving structure.
2. **Importance map**
   - blend gradient/contrast/saliency and user masks; drive adaptive detail.
3. **Segmentation**
   - SLIC superpixels + region merging to obtain boundary-adherent regions.
4. **Boundary simplification**
   - polygonize and simplify while enforcing minimum manufacturable features.
5. **Material-aware quantization**
   - quantize by predicted appearance under chosen lighting/view, not raw RGB alone.
6. **Tessellation family generation**
   - selectable modes: grid, hex/tri, Voronoi, irregular hand-cut library.

---

## Optimization Architecture

### Decision Variables (per tessera)
- Shape/type and scale.
- Material assignment.
- Pose (position, yaw, optional pitch/tilt).

### Hard Constraints
- Non-overlap with grout offsets.
- Boundary containment.
- Inventory and budget limits.
- Thickness compatibility and installation limits.
- Cutting feasibility thresholds.

### Objectives (weighted)
- Appearance error under target lighting/view.
- Material/cost/waste minimization.
- Cutting complexity minimization.
- Orientation smoothness or andamento flow control.

### Solvers
- CP-SAT / MIP for discrete assignment and local re-optimization.
- Greedy constructive solution for interactive feedback.
- Metaheuristics (annealing/GA) for difficult mixed-shape/global refinement.

---

## Rendering Strategy

### Real-time
- glTF-compatible metallic-roughness PBR for interactive previews.

### Offline
- Path-traced hero render for high-confidence material and grout visualization.

### Built-in lighting presets
- Gallery diffuse.
- Raking light.
- Outdoor sun.
- Wet-area interior.

Evaluate design quality at both close-up and intended viewing distance.

---

## Fabrication Outputs

- **Assembly maps**: paginated templates with registration marks, IDs, legends, and grout guidance.
- **Placement sequencing**: multiple strategies (rows, regions, importance-first, etc.).
- **Indirect-method sheets**: grouped patches with cutlines and per-sheet BOM.
- **Orientation aids**: arrows, angle shims, optional jig specs.
- **Cutting layouts**: nesting-ready paths for CNC/manual workflows.

### Export formats
- **SVG**: vector maps and cut paths.
- **PDF**: print booklets and tiled assembly documents.
- **DXF**: CAD/CAM interoperability.
- **glTF**: realtime 3D preview.
- **USDZ**: Apple AR packaging.

---

## Recommended System Architecture

- UI + parameter editor.
- Project model + deterministic versioning.
- Image pipeline.
- Importance/segmentation subsystem.
- Tessellation engine (pluggable families).
- Assignment/optimization engine.
- Manufacturability validator.
- Instruction generator.
- Rendering bridge.
- Exporters.
- Fabrication package bundler.

---

## Internal Data Model (suggested)

`MosaicProject.json`:
- `project_meta`: version, seed, hashes.
- `canvas`: dimensions/boundary/units.
- `materials`: palette entries with PBR fields.
- `tesserae`: polygons, thickness class, pose, IDs, adjacency.
- `constraints`: grout/substrate/cutting/budget/install rules.
- `instructions`: placement order, region sheets, pagination.
- `renders`: preset configs and cached outputs.

---

## Implementation Roadmap

### Phase 1: MVP (beginner manufacturable)
- Grid/hex tessellation.
- Fixed thickness classes.
- Palette quantization + BOM.
- SVG/PDF assembly outputs.

### Phase 2: Fidelity
- Edge-aware preprocessing.
- Importance-driven adaptive sizing.
- Improved dithering and region controls.
- glTF realtime preview.

### Phase 3: Advanced geometry
- Voronoi mode with clipping and relaxation.
- Irregular shape packing (NFP-informed heuristics).
- DXF/CNC-oriented outputs.

### Phase 4: Realism + advanced assembly
- Path-traced offline rendering bridge.
- Optional pitch/tilt optimization with safety checks.
- USDZ/AR guidance overlays.

---

## Product Positioning

- Default mode: conservative, beginner-safe constraints.
- Expert mode: mixed materials/shapes and 3D orientation with stronger warnings and calibration workflows.
- Core value: **aesthetic quality with guaranteed buildability**, not image stylization alone.
