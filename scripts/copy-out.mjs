// Copia o export estatico do Next (frontend/out) para dist/, que e o
// destination_dir configurado no projeto Cloudflare Pages "natodark".
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";

const origem = "frontend/out";
const destino = "dist";

if (!existsSync(origem)) {
  console.error(`Erro: ${origem} nao existe. O next build nao gerou o export estatico.`);
  process.exit(1);
}

rmSync(destino, { recursive: true, force: true });
mkdirSync(destino, { recursive: true });
cpSync(origem, destino, { recursive: true });
console.log(`OK: ${origem} -> ${destino}`);
