import {build} from 'esbuild';
import {copyFile, mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';

const project = resolve(import.meta.dirname);
const output = resolve(project, '../../web/motion');
await mkdir(output, {recursive: true});
await build({
  entryPoints: [resolve(project, 'src/index.jsx')],
  outfile: resolve(output, 'loomq-motion.iife.js'),
  bundle: true,
  minify: true,
  sourcemap: false,
  format: 'iife',
  target: ['es2020'],
  define: {'process.env.NODE_ENV': '"production"'},
});
await copyFile(resolve(project, 'src/motion.css'), resolve(output, 'loomq-motion.css'));
console.log(`Built LoomQ Remotion player into ${output}`);
