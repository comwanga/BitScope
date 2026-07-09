const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const projectDir = fs.realpathSync.native(path.resolve(__dirname, ".."));
const nextBin = path.join(projectDir, "node_modules", "next", "dist", "bin", "next");
const args = process.argv.slice(2);

process.chdir(projectDir);

const result = spawnSync(process.execPath, [nextBin, ...args], {
  cwd: projectDir,
  env: process.env,
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
