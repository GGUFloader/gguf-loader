// Writes electron/dist/package.json for the PyInstaller-bundled launcher.
//
// electron/package.json describes the full dev app (main -> dist/main.js,
// electron-builder scripts). The frozen exe instead launches the standalone
// launcher (electron/standalone.ts -> dist/standalone.js), which just opens
// a BrowserWindow at the running backend's --url. tsc does not emit a
// package.json into dist/, so it is generated here after every compile so
// builds (local AND CI) are reproducible without a hand-made file.
'use strict';

const fs = require('fs');
const path = require('path');

const distDir = path.join(__dirname, '..', 'dist');
const pkg = {
  name: 'gguf-loader-standalone',
  version: '1.0.0',
  main: 'standalone.js',
};

fs.mkdirSync(distDir, { recursive: true });
fs.writeFileSync(
  path.join(distDir, 'package.json'),
  JSON.stringify(pkg, null, 2) + '\n',
  'utf-8'
);
console.log('Wrote electron/dist/package.json (main: standalone.js)');
