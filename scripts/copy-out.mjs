// Copia o export estatico do Next (frontend/out) para dist/, que e o
// destination_dir configurado no projeto Cloudflare Pages "natodark".
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";

const origem = "frontend/out";
const destino = "dist";

if (!existsSync(origem)) {
  console.error(`Erro: ${origem} nao existe. O next build nao gerou o export estatico.`);
  process.exit(1);
}

rmSync(destino, { recursive: true, force: true });
mkdirSync(destino, { recursive: true });
cpSync(origem, destino, { recursive: true });

// So invoca a Pages Function nas rotas /api/*; o resto continua estatico/gratis.
writeFileSync(
  `${destino}/_routes.json`,
  JSON.stringify({ version: 1, include: ["/api/*"], exclude: [] }, null, 2),
);
console.log(`OK: ${origem} -> ${destino} (com _routes.json para /api/*)`);
