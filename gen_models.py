#!/usr/bin/env python3
"""Build .glb (glTF 2.0 binary) models from primitives, no dependencies.

Creates assets/car.glb and assets/still-life.glb.
"""
import json
import math
import os
import struct

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class Buffer:
    """Accumulates binary data and tracks accessors."""

    def __init__(self):
        self.data = bytearray()
        self.accessors = []
        self.buffer_views = []

    def _pad(self, n=4):
        while len(self.data) % n:
            self.data.append(0)

    def add(self, values, component_type, count, type_, target=None):
        """values: flat list of numbers already in the component's shape."""
        self._pad()
        offset = len(self.data)
        fmt = {5120: "<b", 5121: "<B", 5122: "<h", 5123: "<H", 5125: "<I", 5126: "<f"}[component_type]
        for v in values:
            self.data += struct.pack(fmt, v)
        view = {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(self.data) - offset,
        }
        if target:
            view["target"] = target
        self.buffer_views.append(view)
        accessor = {
            "bufferView": len(self.buffer_views) - 1,
            "componentType": component_type,
            "count": count,
            "type": type_,
        }
        self.accessors.append(accessor)
        return len(self.accessors) - 1

    def add_vec3(self, vectors, target=34962):
        flat = [c for v in vectors for c in v]
        acc = self.add(flat, 5126, len(vectors), "VEC3", target)
        mins = [min(v[i] for v in vectors) for i in range(3)]
        maxs = [max(v[i] for v in vectors) for i in range(3)]
        self.accessors[acc].update({"min": mins, "max": maxs})
        return acc

    def add_indices(self, indices, target=34963):
        return self.add(indices, 5125, len(indices), "SCALAR", target)


def box_mesh(size):
    """Unit-box vertex data scaled to size. Returns (positions, normals, indices)."""
    sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
    faces = [
        ((1, 0, 0), [(sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz)]),
        ((-1, 0, 0), [(-sx, -sy, sz), (-sx, sy, sz), (-sx, sy, -sz), (-sx, -sy, -sz)]),
        ((0, 1, 0), [(-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz), (sx, sy, -sz)]),
        ((0, -1, 0), [(-sx, -sy, sz), (-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz)]),
        ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
        ((0, 0, -1), [(sx, -sy, -sz), (-sx, -sy, -sz), (-sx, sy, -sz), (sx, sy, -sz)]),
    ]
    positions, normals, indices = [], [], []
    for n, quad in faces:
        base = len(positions)
        positions.extend(quad)
        normals.extend([n] * 4)
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
    return positions, normals, indices


def sphere_mesh(radius, segments=24, rings=16):
    positions, normals, indices = [], [], []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        y, sr = math.cos(phi), math.sin(phi)
        for s in range(segments + 1):
            theta = 2 * math.pi * s / segments
            x, z = sr * math.cos(theta), sr * math.sin(theta)
            positions.append((radius * x, radius * y, radius * z))
            normals.append((x, y, z))
    for r in range(rings):
        for s in range(segments):
            a = r * (segments + 1) + s
            b = a + segments + 1
            indices.extend([a, b, a + 1, a + 1, b, b + 1])
    return positions, normals, indices


def cylinder_mesh(radius, height, segments=24, axis="y"):
    """Cylinder with caps; smooth side normals, flat cap normals."""
    positions, normals, indices = [], [], []
    half = height / 2
    # side
    for s in range(segments + 1):
        theta = 2 * math.pi * s / segments
        x, z = math.cos(theta), math.sin(theta)
        positions.extend([(radius * x, -half, radius * z), (radius * x, half, radius * z)])
        normals.extend([(x, 0, z), (x, 0, z)])
    for s in range(segments):
        a = 2 * s
        indices.extend([a, a + 1, a + 2, a + 2, a + 1, a + 3])
    # caps
    cap_center = len(positions)
    positions.extend([(0, -half, 0), (0, half, 0)])
    normals.extend([(0, -1, 0), (0, 1, 0)])
    for s in range(segments):
        theta = 2 * math.pi * s / segments
        x, z = radius * math.cos(theta), radius * math.sin(theta)
        positions.extend([(x, -half, z), (x, half, z)])
        normals.extend([(0, -1, 0), (0, 1, 0)])
    for s in range(segments):
        i0 = 2 + 2 * s
        i1 = 2 + 2 * ((s + 1) % segments)
        indices.extend([cap_center, i0, i1])            # bottom
        indices.extend([cap_center + 1, i1 + 1, i0 + 1])  # top (CCW seen from +y)
    if axis == "x":  # rotate y-axis cylinder onto the x axis: (x,y,z) -> (y,-x,z)
        rot = lambda p: (p[1], -p[0], p[2])
        positions = [rot(p) for p in positions]
        normals = [rot(n) for n in normals]
    elif axis == "z":  # rotate y-axis cylinder onto the z axis: (x,y,z) -> (x,-z,y)
        rot = lambda p: (p[0], -p[2], p[1])
        positions = [rot(p) for p in positions]
        normals = [rot(n) for n in normals]
    return positions, normals, indices


def hex_color(h):
    h = h.lstrip("#")
    return [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)] + [1.0]


class Builder:
    def __init__(self):
        self.buf = Buffer()
        self.materials = []
        self.nodes = []
        self.meshes = []

    def material(self, color, metallic=0.0, roughness=0.8, alpha=None, emissive=None):
        mat = {
            "name": f"mat{len(self.materials)}",
            "pbrMetallicRoughness": {
                "baseColorFactor": hex_color(color),
                "metallicFactor": metallic,
                "roughnessFactor": roughness,
            },
        }
        if alpha is not None:
            mat["alphaMode"] = "BLEND"
            base = mat["pbrMetallicRoughness"]["baseColorFactor"]
            mat["pbrMetallicRoughness"]["baseColorFactor"] = base[:3] + [alpha]
        if emissive is not None:
            e = hex_color(emissive)
            mat["emissiveFactor"] = e[:3]
        self.materials.append(mat)
        return len(self.materials) - 1

    def add_primitive(self, positions, normals, indices, mat_index, translation, name):
        pos_acc = self.buf.add_vec3(positions)
        nrm_acc = self.buf.add_vec3(normals)
        idx_acc = self.buf.add_indices(indices)
        self.meshes.append({
            "name": name,
            "primitives": [{
                "attributes": {"POSITION": pos_acc, "NORMAL": nrm_acc},
                "indices": idx_acc,
                "material": mat_index,
            }],
        })
        self.nodes.append({
            "name": name,
            "mesh": len(self.meshes) - 1,
            "translation": list(translation),
        })

    def box(self, size, at, color, **kw):
        self.add_primitive(*box_mesh(size), self.material(color, **kw), at, "box")

    def sphere(self, radius, at, color, **kw):
        self.add_primitive(*sphere_mesh(radius), self.material(color, **kw), at, "sphere")

    def cylinder(self, radius, height, at, color, axis="y", **kw):
        self.add_primitive(*cylinder_mesh(radius, height, axis=axis),
                           self.material(color, **kw), at, "cylinder")

    def save(self, path):
        gltf = {
            "asset": {"version": "2.0", "generator": "hand-written glTF"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": self.materials,
            "accessors": self.buf.accessors,
            "bufferViews": self.buf.buffer_views,
            "buffers": [{"byteLength": len(self.buf.data)}],
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json_bytes = json.dumps(gltf, separators=(",", ":")).encode()
        pad_json = (4 - len(json_bytes) % 4) % 4
        json_bytes += b" " * pad_json
        self.buf._pad(4)
        bin_bytes = bytes(self.buf.data)
        total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
            f.write(json_bytes)
            f.write(struct.pack("<II", len(bin_bytes), 0x004E4942))
            f.write(bin_bytes)
        print(f"wrote {path} ({total} bytes, {len(self.meshes)} meshes)")


def build_car(path):
    b = Builder()
    b.box((4.6, 0.55, 1.9), (0, 0.55, 0), "#d0202a", metallic=0.7, roughness=0.3)
    b.box((4.2, 0.25, 1.96), (0, 0.32, 0), "#8e1218", roughness=0.6)
    b.box((2.1, 0.5, 1.7), (-0.25, 0.95, 0), "#bfe6ff", roughness=0.1, alpha=0.45)
    b.box((1.9, 0.08, 1.5), (-0.25, 1.22, 0), "#d0202a", metallic=0.7, roughness=0.3)
    b.box((0.45, 0.06, 1.6), (-2.25, 0.95, 0), "#d0202a", metallic=0.7, roughness=0.3)
    b.box((0.12, 0.12, 0.12), (-2.25, 0.82, 0.6), "#2a2a2e")
    b.box((0.12, 0.12, 0.12), (-2.25, 0.82, -0.6), "#2a2a2e")
    for z in (0.6, -0.6):
        b.sphere(0.1, (2.26, 0.62, z), "#fff3c4", emissive="#ffedb0")
        b.sphere(0.08, (-2.26, 0.62, z * 1.083), "#ff3535", emissive="#ff2020")
    for x in (1.5, -1.5):
        for z in (0.98, -0.98):
            b.cylinder(0.42, 0.3, (x, 0.42, z), "#1c1c1e", axis="z", roughness=0.9)
            b.cylinder(0.22, 0.31, (x, 0.42, z), "#c8ccd2", axis="z", metallic=1.0, roughness=0.25)
    b.save(path)


def build_still_life(path):
    b = Builder()
    b.box((6, 0.3, 4), (0, -0.25, 0), "#8a5a33", roughness=0.85)
    b.sphere(0.8, (-1.6, 0.55, 0.2), "#d4af37", metallic=1.0, roughness=0.25)
    b.box((1.2, 1.2, 1.2), (1.4, 0.6, -0.2), "#ffffff", roughness=0.05, alpha=0.35)
    b.cylinder(0.18, 0.9, (0.2, 0, 1.4), "#3b3b40", metallic=0.9, roughness=0.3)
    b.sphere(0.3, (0.2, 1.05, 1.4), "#ffb85c", emissive="#ffb050")
    b.save(path)


if __name__ == "__main__":
    build_car(os.path.join(OUT_DIR, "car.glb"))
    build_still_life(os.path.join(OUT_DIR, "still-life.glb"))
