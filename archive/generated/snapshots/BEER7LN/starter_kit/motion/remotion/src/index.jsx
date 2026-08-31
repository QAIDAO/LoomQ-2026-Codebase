import React, {createRef} from 'react';
import {createRoot} from 'react-dom/client';
import {Player} from '@remotion/player';
import {LoomQMotion} from './LoomQMotion.jsx';

const mounted = new WeakMap();

function render(instance) {
  const {root, playerRef, inputProps} = instance;
  root.render(<Player
    ref={playerRef}
    component={LoomQMotion}
    inputProps={inputProps}
    durationInFrames={1}
    compositionWidth={1280}
    compositionHeight={720}
    fps={30}
    controls={false}
    autoPlay={false}
    loop={false}
    initialFrame={0}
    clickToPlay={false}
    acknowledgeRemotionLicense
    style={{width: '100%', aspectRatio: '16 / 9'}}
  />);
}

function mount(container, inputProps = {}) {
  const existing = mounted.get(container);
  const instance = existing || {root: createRoot(container), playerRef: createRef(), inputProps: {}};
  instance.inputProps = {...inputProps, stepIndex: Number(inputProps.stepIndex) || 0};
  render(instance);
  mounted.set(container, instance);
  return true;
}

function setStep(container, stepIndex) {
  const instance = mounted.get(container);
  if (!instance) return false;
  instance.inputProps = {...instance.inputProps, stepIndex: Math.max(0, Number(stepIndex) || 0)};
  render(instance);
  return true;
}

function pause(container) {
  return mounted.has(container);
}

function unmount(container) {
  const instance = mounted.get(container);
  if (!instance) return false;
  instance.root.unmount();
  mounted.delete(container);
  return true;
}

globalThis.LoomQMotion = Object.freeze({mount, setStep, pause, unmount});
