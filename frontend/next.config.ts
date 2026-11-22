import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cloudflare Pages serve arquivos estáticos; o backend/API fica no Worker.
  output: "export",
};

export default nextConfig;
