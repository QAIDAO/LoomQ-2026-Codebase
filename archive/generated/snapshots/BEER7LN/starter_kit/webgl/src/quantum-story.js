import * as THREE from "three";

const canvas = document.querySelector("#quantumStoryCanvas");
const story = document.querySelector("#quantumStory");
const stage = story?.querySelector(".story-stage");
const welcomeScreen = story?.closest('[data-screen="welcome"]');
const frames = [...document.querySelectorAll("[data-story-scene]")];

if (canvas && story) {
  const reducedMotion = globalThis.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
  const mobile = globalThis.matchMedia?.("(max-width: 760px)")?.matches ?? false;
  const count = mobile ? 5200 : 14000;
  const pointer = new THREE.Vector2();
  const targetPointer = new THREE.Vector2();
  let renderer;

  try {
    renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: !mobile,
      powerPreference: "high-performance",
    });
  } catch {
    story.classList.add("webgl-fallback");
  }

  if (renderer) {
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x07080c, 0.055);
    const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 80);
    camera.position.set(0, 0.4, 14);

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const seeds = new Float32Array(count * 4);

    function fract(value) {
      return value - Math.floor(value);
    }

    for (let index = 0; index < count; index += 1) {
      const u = fract((index + 1) * 0.618033988749895);
      const v = fract((index + 1) * 0.754877666246693);
      const w = fract((index + 1) * 0.569840290998053);
      const q = fract((index + 1) * 0.438579021);
      const offset = index * 3;
      const seedOffset = index * 4;
      positions[offset] = (u - 0.5) * 20;
      positions[offset + 1] = (v - 0.5) * 11;
      positions[offset + 2] = (w - 0.5) * 8;
      seeds[seedOffset] = u;
      seeds[seedOffset + 1] = v;
      seeds[seedOffset + 2] = w;
      seeds[seedOffset + 3] = q;
    }

    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 4));

    const vertexShader = [
      "uniform float uProgress;",
      "uniform float uTime;",
      "uniform vec2 uPointer;",
      "attribute vec4 aSeed;",
      "varying float vAlpha;",
      "varying float vGlow;",
      "float ease(float value) { return value * value * (3.0 - 2.0 * value); }",
      "void main() {",
      "  vec3 stars = position;",
      "  stars.y -= 1.1 + abs(stars.x) * 0.035;",
      "  vec3 classical = vec3(-3.4 + (aSeed.x - 0.5) * 1.6, -2.4 + pow(aSeed.y, 2.0) * 4.2, (aSeed.z - 0.5) * 2.2);",
      "  float branch = aSeed.x < 0.5 ? -1.0 : 1.0;",
      "  vec3 superposed = vec3(branch * (2.8 + aSeed.y * 1.8) + (aSeed.z - 0.5) * 1.4, -1.4 + sin(aSeed.y * 10.0) * 0.45 + aSeed.w * 2.8, (aSeed.z - 0.5) * 3.0);",
      "  float waveX = (aSeed.x - 0.5) * 16.0;",
      "  float phase = 3.14159265 * smoothstep(0.52, 0.70, uProgress);",
      "  float pathA = sin(waveX * 1.45 + uTime * 0.22);",
      "  float pathB = sin(waveX * 1.45 + phase - uTime * 0.22);",
      "  vec3 interference = vec3(waveX, -1.0 + (pathA + pathB) * 1.15 + (aSeed.y - 0.5) * 1.2, (aSeed.z - 0.5) * 3.2);",
      "  float binX = aSeed.x < 0.46 ? -4.5 : (aSeed.x < 0.50 ? -1.5 : (aSeed.x < 0.54 ? 1.5 : 4.5));",
      "  float binHeight = (abs(binX) > 3.0 ? 5.2 : 0.55);",
      "  vec3 measured = vec3(binX + (aSeed.z - 0.5) * 1.35, -3.2 + aSeed.y * binHeight, (aSeed.w - 0.5) * 2.1);",
      "  float toClassical = ease(smoothstep(0.08, 0.25, uProgress));",
      "  float toSuperposed = ease(smoothstep(0.25, 0.46, uProgress));",
      "  float toInterference = ease(smoothstep(0.46, 0.72, uProgress));",
      "  float toMeasured = ease(smoothstep(0.72, 0.94, uProgress));",
      "  vec3 transformed = mix(stars, classical, toClassical);",
      "  transformed = mix(transformed, superposed, toSuperposed);",
      "  transformed = mix(transformed, interference, toInterference);",
      "  transformed = mix(transformed, measured, toMeasured);",
      "  transformed.xy += uPointer * vec2(0.34, 0.2) * (1.0 - toMeasured * 0.65);",
      "  transformed.y += sin(uTime * 0.35 + aSeed.w * 18.0) * 0.04 * (1.0 - toMeasured);",
      "  vec4 viewPosition = modelViewMatrix * vec4(transformed, 1.0);",
      "  gl_Position = projectionMatrix * viewPosition;",
      "  float depthScale = 30.0 / max(3.0, -viewPosition.z);",
      "  gl_PointSize = (1.1 + aSeed.w * 2.1) * depthScale;",
      "  vAlpha = 0.28 + aSeed.y * 0.64;",
      "  vGlow = mix(0.25, 1.0, toInterference * (0.35 + 0.65 * abs(pathA + pathB) * 0.5));",
      "}",
    ].join("\n");

    const fragmentShader = [
      "precision highp float;",
      "varying float vAlpha;",
      "varying float vGlow;",
      "void main() {",
      "  vec2 centered = gl_PointCoord - vec2(0.5);",
      "  float radius = length(centered);",
      "  float alpha = smoothstep(0.5, 0.08, radius) * vAlpha;",
      "  vec3 cool = vec3(0.72, 0.68, 1.0);",
      "  vec3 mint = vec3(0.49, 0.96, 0.84);",
      "  vec3 color = mix(cool, mint, vGlow * 0.48);",
      "  gl_FragColor = vec4(color, alpha);",
      "}",
    ].join("\n");

    const material = new THREE.ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        uProgress: {value: 0},
        uTime: {value: 0},
        uPointer: {value: pointer},
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    const particleField = new THREE.Points(geometry, material);
    particleField.rotation.x = -0.08;
    scene.add(particleField);

    let scrollProgress = 0;
    let renderedProgress = 0;
    let storyTop = 0;
    let storyDistance = 1;
    let frameAnchors = [];
    let lastScene = -1;

    function measureStory() {
      const bounds = story.getBoundingClientRect();
      storyTop = bounds.top + globalThis.scrollY;
      storyDistance = Math.max(1, story.offsetHeight - globalThis.innerHeight);
      frameAnchors = frames.map((frame) => storyTop + frame.offsetTop + frame.offsetHeight * 0.5);
      const width = Math.max(1, stage?.clientWidth || globalThis.innerWidth);
      const height = Math.max(1, stage?.clientHeight || globalThis.innerHeight);
      renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, mobile ? 1.25 : 1.75));
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      updateScroll();
    }

    function updateScroll() {
      scrollProgress = THREE.MathUtils.clamp((globalThis.scrollY - storyTop) / storyDistance, 0, 1);
      updateActiveScene();
    }

    function updateActiveScene() {
      const viewportAnchor = globalThis.scrollY + globalThis.innerHeight * 0.52;
      const sceneIndex = frameAnchors.reduce((nearest, anchor, index) => (
        Math.abs(anchor - viewportAnchor) < Math.abs(frameAnchors[nearest] - viewportAnchor) ? index : nearest
      ), 0);
      if (sceneIndex === lastScene) return;
      lastScene = sceneIndex;
      story.dataset.activeScene = String(sceneIndex);
      frames.forEach((frame, index) => {
        frame.classList.toggle("is-current", index === sceneIndex);
        if (index === sceneIndex) frame.setAttribute("aria-current", "step");
        else frame.removeAttribute("aria-current");
      });
    }

    function onPointerMove(event) {
      targetPointer.x = (event.clientX / globalThis.innerWidth - 0.5) * 2;
      targetPointer.y = (0.5 - event.clientY / globalThis.innerHeight) * 2;
    }

    function render(timestamp) {
      const visible = !document.hidden && !welcomeScreen?.hidden;
      if (visible) {
        renderedProgress = reducedMotion
          ? scrollProgress
          : THREE.MathUtils.lerp(renderedProgress, scrollProgress, 0.075);
        pointer.lerp(targetPointer, reducedMotion ? 1 : 0.045);
        material.uniforms.uProgress.value = renderedProgress;
        material.uniforms.uTime.value = reducedMotion ? 0 : timestamp * 0.001;
        camera.position.x = pointer.x * 0.32;
        camera.position.y = 0.35 + pointer.y * 0.18;
        camera.lookAt(0, -0.25, 0);
        renderer.render(scene, camera);
      }
      globalThis.requestAnimationFrame(render);
    }

    globalThis.addEventListener("resize", measureStory, {passive: true});
    globalThis.addEventListener("scroll", updateScroll, {passive: true});
    globalThis.addEventListener("pointermove", onPointerMove, {passive: true});
    globalThis.addEventListener("loomq:screen-change", measureStory);
    measureStory();
    story.classList.add("webgl-ready");
    render(0);
  }
}