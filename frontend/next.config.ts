import type { NextConfig } from "next";
import { realpathSync } from "fs";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: realpathSync.native(process.cwd())
};

export default nextConfig;
