import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { homedir } from 'node:os';

const isWindows = process.platform === 'win32';
const javaBin = isWindows ? 'java.exe' : 'java';
const pathKey = Object.keys(process.env).find(key => key.toLowerCase() === 'path') || 'PATH';

function javaMajor(javaPath) {
  const result = spawnSync(javaPath, ['-version'], { encoding: 'utf8' });
  const output = `${result.stderr || ''}\n${result.stdout || ''}`;
  const match = output.match(/version "(\d+)/) || output.match(/openjdk version "(\d+)/);
  return match ? Number(match[1]) : 0;
}

function hasHttpServerModule(javaPath) {
  const result = spawnSync(javaPath, ['--list-modules'], { encoding: 'utf8' });
  const output = `${result.stderr || ''}\n${result.stdout || ''}`;
  return output.includes('jdk.httpserver@');
}

function isUsableJava(javaPath) {
  return javaMajor(javaPath) >= 21 && hasHttpServerModule(javaPath);
}

function collectJavaCandidates(root, maxDepth = 5, depth = 0, found = []) {
  if (!root || depth > maxDepth || !existsSync(root)) return found;

  for (const entry of readdirSync(root)) {
    const path = join(root, entry);
    try {
      const stat = statSync(path);
      if (stat.isFile() && entry.toLowerCase() === javaBin.toLowerCase()) found.push(path);
      else if (stat.isDirectory()) collectJavaCandidates(path, maxDepth, depth + 1, found);
    } catch {
      // Ignore unreadable folders.
    }
  }

  return found;
}

function findJava21() {
  const javaHome = process.env.JAVA_HOME ? join(process.env.JAVA_HOME, 'bin', javaBin) : '';
  const explicit = [javaHome, isWindows ? 'java.exe' : 'java'].filter(Boolean);

  for (const candidate of explicit) {
    if (isUsableJava(candidate)) return candidate;
  }

  const home = homedir();
  const roots = [
    join(home, '.vscode', 'extensions'),
    join(home, '.antigravity', 'extensions'),
    join(home, '.gradle', 'jdks'),
    isWindows ? 'C:\\Program Files\\Android\\Android Studio\\jbr\\bin' : ''
  ].filter(Boolean);

  for (const root of roots) {
    const candidates = collectJavaCandidates(root);
    for (const candidate of candidates) {
      if (isUsableJava(candidate)) return candidate;
    }
  }

  return null;
}

const java21 = findJava21();

if (!java21) {
  console.error('Firebase Emulator precisa de um JDK 21+ completo com o módulo jdk.httpserver. Instale um JDK 21 ou configure JAVA_HOME.');
  process.exit(1);
}

process.env[pathKey] = `${dirname(java21)}${isWindows ? ';' : ':'}${process.env[pathKey] || ''}`;
process.env.JAVA_TOOL_OPTIONS = `${process.env.JAVA_TOOL_OPTIONS || ''} --add-modules=jdk.httpserver`.trim();

const firebaseToolsPackage = join(process.cwd(), 'node_modules', 'firebase-tools', 'package.json');
const firebaseTools = JSON.parse(readFileSync(firebaseToolsPackage, 'utf8'));
const firebaseBin = join(dirname(firebaseToolsPackage), firebaseTools.bin.firebase);

const child = spawn(
  process.execPath,
  [
    firebaseBin,
    'emulators:exec',
    '--project',
    'demo-healplus',
    '--only',
    'auth,firestore,storage',
    'vitest run src/tests/rules'
  ],
  { stdio: 'inherit', env: process.env }
);
child.on('exit', code => process.exit(code ?? 1));
