# threejs-3d-model-viewer

A minimal, dependency-free 3D model viewer built with three.js and glTF.

The models are **hand-generated**: `gen_models.py` writes valid glTF 2.0 binary
(`.glb`) files from scratch - no mesh libraries, just boxes, spheres and
cylinders with PBR materials (metallic paint, emissive lights, translucent glass).

## Models

| Model | File | Meshes |
|---|---|---|
| Concept Roadster | `assets/car.glb` | 19 |
| Desk Still-life | `assets/still-life.glb` | 5 |

## Run

```sh
python3 -m http.server 8137
```

Then open <http://localhost:8137>.

- Drag to orbit, scroll to zoom, right-drag to pan
- Switch models with the sidebar buttons

## Regenerating the models

```sh
python3 gen_models.py
```

## Structure

```
assets/        generated .glb models
libs/          vendored three.js r160 (works offline)
index.html     viewer UI
main.js        scene, lighting, orbit camera, model loading
gen_models.py  glTF binary writer + model definitions
```
