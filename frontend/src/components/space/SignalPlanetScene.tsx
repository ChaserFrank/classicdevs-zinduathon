/**
 * The 3D Signal Planet (lazy-loaded; ~600 kB of three.js never reaches app screens).
 * Evidence dots on a dark violet body, an orange fresnel rim with a soft bloom, Kenya facing the
 * viewer with a pulse at Nairobi, and a one-time "noise → signal" intro.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import {
  easeOutCubic,
  landPoints,
  latLonToVec,
  NAIROBI,
  seeded,
  type LandMask,
  type Vec3,
} from "./planet-geometry";

const COLORS = {
  planet: new THREE.Color("#170A28"),
  planet2: new THREE.Color("#2A1745"),
  ember: new THREE.Color("#C2410C"),
  flare: new THREE.Color("#FF7A1A"),
  flareHot: new THREE.Color("#FFB15C"),
  mist: new THREE.Color("#A0A0AC"),
};
const LATTICE = 16000;
const INTRO_PARTICLES = 1500;
const INTRO_SECONDS = 2.4;
const TURN_SECONDS = 240; // one full turn per ~4 minutes
const PLANET_Y = -1.32; // sphere centre (radius 1): only the top cap rises into view
const PLANET_TOP_Y = PLANET_Y + 1;

export type SceneProps = {
  /** Play the noise → signal intro (first visit only; never with reduced motion). */
  intro: boolean;
  /** Called once the intro has landed, so the headline can fade up. */
  onIntroDone?: () => void;
  /** Stop rendering (tab hidden or off-screen). */
  paused: boolean;
  /** Transparent background, used to capture the static fallback image. */
  capture?: boolean;
};

async function loadMask(): Promise<LandMask> {
  const image = new Image();
  image.src = "/textures/land-mask.png";
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.width;
  canvas.height = image.height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("2D canvas unavailable");
  ctx.drawImage(image, 0, 0);
  return {
    width: image.width,
    height: image.height,
    data: ctx.getImageData(0, 0, image.width, image.height).data,
  };
}

const dotVertex = /* glsl */ `
  attribute vec3 aStart;
  attribute float aSize;
  attribute float aIntro;
  uniform float uProgress;
  uniform float uPixelRatio;
  varying float vMix;
  void main() {
    float t = aIntro > 0.5 ? uProgress : 1.0;
    vec3 p = mix(aStart, position, t);
    vMix = t;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * uPixelRatio * (3.2 / -mv.z);
  }
`;
const dotFragment = /* glsl */ `
  uniform vec3 uMist;
  varying float vMix;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float alpha = smoothstep(0.5, 0.25, d) * mix(0.55, 0.85, vMix);
    gl_FragColor = vec4(mix(uMist, vec3(1.0), vMix), alpha);
  }
`;
const bodyFragment = /* glsl */ `
  uniform vec3 uPlanet; uniform vec3 uPlanet2; uniform vec3 uEmber; uniform vec3 uFlare;
  varying vec3 vNormal; varying vec3 vView;
  void main() {
    float facing = clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0);
    vec3 body = mix(uPlanet, uPlanet2, smoothstep(0.2, 1.0, facing) * 0.6);
    // The limb burns: a wide ember band that turns flare-hot right at the edge (reference rim).
    float inner = pow(1.0 - facing, 2.2);
    vec3 rimCol = mix(uEmber, uFlare, smoothstep(0.25, 0.8, inner));
    vec3 col = body + rimCol * inner * 1.35 + uFlare * pow(1.0 - facing, 8.0) * 0.8;
    gl_FragColor = vec4(col, 1.0);
  }
`;
const haloVertex = /* glsl */ `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
`;
// Glow outside the silhouette: smooth exponential falloff, dithered to avoid banding rings.
const haloFragment = /* glsl */ `
  uniform vec3 uEmber; uniform vec3 uFlare; uniform vec3 uHot; uniform float uEdge;
  varying vec2 vUv;
  float rand(vec2 co) { return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453); }
  void main() {
    float r = length(vUv - 0.5) * 2.0 * 1.9;     // plane is 3.8 units wide → r in sphere radii
    float d = max(r - uEdge, 0.0);
    // Starts just under the limb (the body hides the inside), so there's no gap at the edge.
    float g = exp(-d * 8.0) * 0.95 + exp(-d * 2.6) * 0.2;
    vec3 col = mix(uEmber, mix(uFlare, uHot, exp(-d * 18.0)), exp(-d * 4.0));
    g += (rand(gl_FragCoord.xy) - 0.5) / 255.0 * 2.0;
    gl_FragColor = vec4(col * g, g);
  }
`;
const normalVertex = /* glsl */ `
  varying vec3 vNormal; varying vec3 vView;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalMatrix * normal;
    vView = -mv.xyz;
    gl_Position = projectionMatrix * mv;
  }
`;

function Dots({ mask, intro, onIntroDone }: { mask: LandMask; intro: boolean; onIntroDone?: () => void }) {
  const { viewport, gl } = useThree();
  const material = useRef<THREE.ShaderMaterial>(null);
  const started = useRef<number | null>(null);
  const done = useRef(!intro);

  const geometry = useMemo(() => {
    const points = landPoints(mask, LATTICE);
    const rand = seeded(42);
    const positions = new Float32Array(points.length * 3);
    const starts = new Float32Array(points.length * 3);
    const sizes = new Float32Array(points.length);
    const introFlags = new Float32Array(points.length);
    // Pick evenly spread points to fly in from the edges of the screen.
    const every = Math.max(1, Math.floor(points.length / INTRO_PARTICLES));
    points.forEach((p, i) => {
      positions.set(p, i * 3);
      sizes[i] = 2.2 + rand() * 1.4;
      if (intro && i % every === 0) {
        introFlags[i] = 1;
        const angle = rand() * Math.PI * 2;
        const dist = 2.2 + rand() * 1.6;
        starts.set(
          [Math.cos(angle) * dist * 1.6, Math.sin(angle) * dist + 0.8, 0.4 + rand() * 0.8] as Vec3,
          i * 3,
        );
      } else {
        starts.set(p, i * 3);
      }
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("aStart", new THREE.BufferAttribute(starts, 3));
    g.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    g.setAttribute("aIntro", new THREE.BufferAttribute(introFlags, 1));
    return g;
  }, [mask, intro]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(({ clock }) => {
    const m = material.current;
    if (!m) return;
    if (started.current === null) started.current = clock.elapsedTime;
    const t = intro ? (clock.elapsedTime - started.current) / INTRO_SECONDS : 1;
    m.uniforms.uProgress!.value = easeOutCubic(t);
    if (!done.current && t >= 1) {
      done.current = true;
      onIntroDone?.();
    }
  });

  return (
    <points geometry={geometry} renderOrder={2}>
      <shaderMaterial
        ref={material}
        vertexShader={dotVertex}
        fragmentShader={dotFragment}
        transparent
        depthWrite={false}
        uniforms={{
          uProgress: { value: intro ? 0 : 1 },
          uPixelRatio: { value: gl.getPixelRatio() * Math.max(1, viewport.dpr / gl.getPixelRatio()) },
          uMist: { value: COLORS.mist },
        }}
      />
    </points>
  );
}

function NairobiPulse() {
  const ring = useRef<THREE.Mesh>(null);
  const position = useMemo(
    () => new THREE.Vector3(...latLonToVec(NAIROBI.lat, NAIROBI.lon)).multiplyScalar(1.003),
    [],
  );
  const quaternion = useMemo(
    () => new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), position.clone().normalize()),
    [position],
  );
  useFrame(({ clock }) => {
    const mesh = ring.current;
    if (!mesh) return;
    const phase = (clock.elapsedTime % 4) / 4; // every 4 s
    const scale = 0.01 + phase * 0.07;
    mesh.scale.setScalar(scale / 0.05);
    (mesh.material as THREE.MeshBasicMaterial).opacity = (1 - phase) * 0.9;
  });
  return (
    <group position={position} quaternion={quaternion}>
      <mesh>
        <circleGeometry args={[0.012, 16]} />
        <meshBasicMaterial color={COLORS.flareHot} />
      </mesh>
      <mesh ref={ring}>
        <ringGeometry args={[0.04, 0.05, 48]} />
        <meshBasicMaterial color={COLORS.flareHot} transparent depthWrite={false} />
      </mesh>
    </group>
  );
}

function Stars() {
  const group = useRef<THREE.Points>(null);
  const material = useRef<THREE.PointsMaterial>(null);
  const geometry = useMemo(() => {
    const rand = seeded(7);
    const pos = new Float32Array(420 * 3);
    for (let i = 0; i < 420; i++) pos.set([(rand() - 0.5) * 14, (rand() - 0.2) * 7, -4 - rand() * 3], i * 3);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);
  useFrame(({ clock, pointer }) => {
    if (material.current) material.current.opacity = 0.55 + Math.sin(clock.elapsedTime * 0.8) * 0.15;
    if (group.current) {
      // Gentle parallax (a few pixels at most).
      group.current.position.x += (pointer.x * 0.06 - group.current.position.x) * 0.05;
      group.current.position.y += (pointer.y * 0.04 - group.current.position.y) * 0.05;
    }
  });
  return (
    <points ref={group} geometry={geometry}>
      <pointsMaterial ref={material} size={0.018} color="#ffffff" transparent depthWrite={false} />
    </points>
  );
}

/**
 * Keep the planet's proportions on any screen: on wide screens it spans ~60% of the width (as in
 * the reference); on portrait phones the camera pulls back so it spans ~115% instead of ~250%.
 */
function ResponsiveCamera() {
  const { camera, size } = useThree();
  useEffect(() => {
    const aspect = size.width / size.height;
    const halfFov = ((38 / 2) * Math.PI) / 180;
    const wantedWidth = aspect >= 1.2 ? 0.6 : 1.15; // planet diameter / viewport width
    const z = Math.max(3.1, 2 / (wantedWidth * 2 * Math.tan(halfFov) * aspect));
    // Portrait: raise the camera so only the planet's top cap (~45% of it) shows above the
    // bottom edge, like the reference. topFraction = cap height / viewport height.
    let y = 0;
    if (aspect < 1.2) {
      const halfHeight = z * Math.tan(halfFov);
      const topFraction = 0.45 * wantedWidth * aspect;
      y = PLANET_TOP_Y + halfHeight * (1 - 2 * topFraction);
    }
    camera.position.set(0, y, z);
    camera.updateProjectionMatrix();
  }, [camera, size.width, size.height]);
  return null;
}

function Planet({ mask, intro, onIntroDone }: { mask: LandMask; intro: boolean; onIntroDone?: () => void }) {
  const spin = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (spin.current) spin.current.rotation.y += (delta * Math.PI * 2) / TURN_SECONDS;
  });
  const uniforms = useMemo(
    () => ({
      uPlanet: { value: COLORS.planet },
      uPlanet2: { value: COLORS.planet2 },
      uEmber: { value: COLORS.ember },
      uFlare: { value: COLORS.flare },
      uHot: { value: COLORS.flareHot },
    }),
    [],
  );
  return (
    <group position={[0, PLANET_Y, 0]}>
      <Halo uniforms={uniforms} />
      {/* Tilted toward the viewer so Kenya (on the equator) rises into the visible cap. */}
      <group rotation={[-0.85, 0, 0]}>
        <group ref={spin}>
          <mesh renderOrder={1}>
            <sphereGeometry args={[0.995, 96, 96]} />
            <shaderMaterial vertexShader={normalVertex} fragmentShader={bodyFragment} uniforms={uniforms} />
          </mesh>
          <Dots mask={mask} intro={intro} onIntroDone={onIntroDone} />
          <NairobiPulse />
        </group>
      </group>
    </group>
  );
}

/** Camera-facing disc behind the planet carrying the outer glow (no banding, unlike a fresnel shell). */
function Halo({ uniforms }: { uniforms: Record<string, { value: unknown }> }) {
  const mesh = useRef<THREE.Mesh>(null);
  const { camera } = useThree();
  const haloUniforms = useMemo(() => ({ ...uniforms, uEdge: { value: 0.985 } }), [uniforms]);
  useFrame(() => mesh.current?.quaternion.copy(camera.quaternion));
  return (
    <mesh ref={mesh} renderOrder={0}>
      <planeGeometry args={[3.8, 3.8]} />
      <shaderMaterial
        vertexShader={haloVertex}
        fragmentShader={haloFragment}
        uniforms={haloUniforms}
        blending={THREE.AdditiveBlending}
        transparent
        depthWrite={false}
      />
    </mesh>
  );
}

export default function SignalPlanetScene({ intro, onIntroDone, paused, capture }: SceneProps) {
  const [mask, setMask] = useState<LandMask | null>(null);
  useEffect(() => {
    let alive = true;
    loadMask().then(
      (m) => alive && setMask(m),
      () => undefined,
    );
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Canvas
      dpr={[1, 1.75]}
      // "demand" (not "never") when paused: still draws one frame, so an off-screen planet isn't blank.
      frameloop={paused ? "demand" : "always"}
      camera={{ position: [0, 0, 3.1], fov: 38 }}
      gl={{
        antialias: true,
        alpha: true,
        powerPreference: "high-performance",
        preserveDrawingBuffer: capture,
      }}
      style={{ background: "transparent" }}
      aria-hidden
    >
      <ResponsiveCamera />
      {!capture && <Stars />}
      {mask && <Planet mask={mask} intro={intro} onIntroDone={onIntroDone} />}
      <EffectComposer multisampling={0} enableNormalPass={false}>
        <Bloom intensity={0.55} luminanceThreshold={0.25} luminanceSmoothing={0.4} mipmapBlur />
      </EffectComposer>
    </Canvas>
  );
}
