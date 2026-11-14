import * as THREE from "three";
import { OrbitControls } from "./libs/OrbitControls.js";
import { GLTFLoader } from "./libs/GLTFLoader.js";

const MODELS = [
  { name: "Concept Roadster", file: "assets/car.glb" },
  { name: "Desk Still-life", file: "assets/still-life.glb" },
];

const viewport = document.getElementById("viewport");
const loaderEl = document.getElementById("loader");

// --- renderer / scene / camera ---
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled = true;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x101216);
scene.fog = new THREE.Fog(0x101216, 14, 40);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
camera.position.set(5, 3, 6);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 0.6, 0);

// --- lights ---
scene.add(new THREE.HemisphereLight(0x7788aa, 0x1a1c22, 0.4));
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(5, 8, 4);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -8;
key.shadow.camera.right = 8;
key.shadow.camera.top = 8;
key.shadow.camera.bottom = -8;
scene.add(key);
const rim = new THREE.DirectionalLight(0x6688ff, 0.8);
rim.position.set(-6, 4, -5);
scene.add(rim);

// --- ground + grid ---
const ground = new THREE.Mesh(
  new THREE.CircleGeometry(12, 64),
  new THREE.MeshStandardMaterial({ color: 0x14161b, roughness: 0.75, metalness: 0.0 })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);
const grid = new THREE.GridHelper(24, 24, 0x33384a, 0x242836);
grid.position.y = 0.001;
scene.add(grid);

// --- model loading ---
const gltfLoader = new GLTFLoader();
let current = null;

function loadModel(file) {
  loaderEl.classList.add("show");
  if (current) {
    scene.remove(current);
    current.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
    });
    current = null;
  }
  gltfLoader.load(
    file,
    (gltf) => {
      const model = gltf.scene;
      // fit model into a ~4-unit box and center it
      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3()).length();
      const scale = 4 / size;
      model.scale.setScalar(scale);
      box.setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      model.position.sub(center);
      box.setFromObject(model);
      model.position.y -= box.min.y; // sit on the ground
      model.traverse((o) => {
        if (o.isMesh) {
          o.castShadow = true;
          o.receiveShadow = true;
          const m = o.material;
          if (m && m.transparent && m.opacity < 0.7) {
            o.material.transparent = true;
          }
        }
      });
      current = model;
      scene.add(model);
      loaderEl.classList.remove("show");
    },
    undefined,
    (err) => {
      loaderEl.textContent = "Failed to load: " + file;
      console.error(err);
    }
  );
}

// --- UI ---
const list = document.getElementById("model-list");
MODELS.forEach((m, i) => {
  const btn = document.createElement("button");
  btn.className = "model-btn" + (i === 0 ? " active" : "");
  btn.textContent = m.name;
  btn.addEventListener("click", () => {
    list.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadModel(m.file);
  });
  list.appendChild(btn);
});

// --- resize + loop ---
function resize() {
  const w = viewport.clientWidth;
  const h = viewport.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
window.addEventListener("resize", resize);
resize();

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});

loadModel(MODELS[0].file);
