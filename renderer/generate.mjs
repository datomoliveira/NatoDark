// Gera um projeto HyperFrames a partir da timeline ja normalizada do NatoDark.
// Uso: node generate.mjs <spec.json> <pasta-do-projeto>
// A timeline ja vem com duration/trim resolvidos e arquivos locais; aqui so
// copiamos os arquivos para assets/ e escrevemos o HTML com data-start/duration.

import fs from "node:fs";
import path from "node:path";

const [specPath, destino] = process.argv.slice(2);
if (!specPath || !destino) {
  console.error("Uso: node generate.mjs <spec.json> <pasta-do-projeto>");
  process.exit(2);
}

const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const width = Number(spec.width) || 1920;
const height = Number(spec.height) || 1080;
const fps = Number(spec.fps) || 30;
const itens = Array.isArray(spec.items) ? spec.items : [];
if (!itens.length) throw new Error("A spec nao continha itens para renderizar.");

fs.mkdirSync(path.join(destino, "assets"), { recursive: true });

let relogio = 0;
const clipes = [];
for (const [indice, item] of itens.entries()) {
  const origem = String(item.path || "");
  if (!fs.existsSync(origem)) throw new Error(`Arquivo de midia nao encontrado: ${origem}`);
  const extensao = path.extname(origem).toLowerCase() || (item.type === "image" ? ".png" : ".mp4");
  const nome = `clip_${String(indice).padStart(3, "0")}${extensao}`;
  fs.copyFileSync(origem, path.join(destino, "assets", nome));
  const duracao = Math.max(0.04, Number(item.duration) || 5);
  clipes.push({ nome, type: item.type === "image" ? "image" : "video", start: relogio, duration: duracao });
  relogio += duracao;
}

const duracao_total = Math.max(0.1, relogio);
const marcas = clipes
  .map((c, i) => {
    const atributos = `class="clip" id="clip-${i}" src="assets/${c.nome}" data-start="${c.start.toFixed(3)}" data-duration="${c.duration.toFixed(3)}" data-track-index="0"`;
    return c.type === "image"
      ? `      <img ${atributos} alt="" />`
      : `      <video ${atributos} muted playsinline preload="auto"></video>`;
  })
  .join("\n");

const html = `<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=${width}, height=${height}" />
    <title>NatoDark · HyperFrames</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: ${width}px; height: ${height}px; overflow: hidden; background: #000; }
      #root { position: relative; width: 100%; height: 100%; background: #000; }
      #root .clip { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="natodark" data-start="0" data-duration="${duracao_total.toFixed(3)}"
         data-fps="${fps}" data-width="${width}" data-height="${height}">
${marcas}
    </div>
    <script>window.__timelines = window.__timelines || {}; window.__timelines["natodark"] = { seek() {} };</script>
  </body>
</html>
`;

fs.writeFileSync(path.join(destino, "index.html"), html, "utf8");
fs.writeFileSync(
  path.join(destino, "hyperframes.json"),
  JSON.stringify(
    {
      $schema: "https://hyperframes.com/schema/hyperframes.json",
      paths: { assets: "assets" },
      media: { autoProxy: true },
    },
    null,
    2,
  ) + "\n",
  "utf8",
);
fs.writeFileSync(
  path.join(destino, "package.json"),
  JSON.stringify({ name: "natodark-render", private: true, type: "module" }, null, 2) + "\n",
  "utf8",
);

console.log(`Composicao HyperFrames gerada: ${clipes.length} clipes, ${duracao_total.toFixed(2)}s em ${destino}`);
