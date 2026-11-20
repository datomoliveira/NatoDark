// Prompt e normalizacao compartilhados com backend/script_generator.py.
// Manter os dois em sincronia garante o mesmo formato de saida na Cloudflare
// e no computador local.

export const TIPOS_BLOCO = ["hook", "promessa", "giro", "prova", "cliffhanger", "cta"] as const;
type TipoBloco = (typeof TIPOS_BLOCO)[number];

export const SYSTEM_PROMPT = `Voce e um roteirista senior de YouTube para o mercado brasileiro,
especialista em retencao nos primeiros 60 segundos. Voce escreve somente em
portugues do Brasil, oral e natural. NUNCA use portugues de Portugal.

REGRAS DE RETENCAO (obedeca todas):
1. HOOK: a primeira fala comeca no segundo 0. Sem saudacao, sem "oi gente", sem
   "bem-vindos", sem apresentar o canal. Comece com pergunta incomoda,
   contradicao ou afirmacao ousada.
2. FRASES FALADAS: no maximo 12 a 15 palavras por bloco. Escreva como se
   estivesse falando, nao como texto de artigo.
3. CURIOSIDADE: abra uma pergunta no comeco e va respondendo aos poucos.
   Nunca responda tudo no primeiro bloco.
4. PATTERN INTERRUPT: a cada 5 a 8 segundos mude de ritmo, cena ou estilo de
   fala. Descreva isso no campo sugestao_visual.
5. CLIFFHANGER: antes de cada virada, use uma frase que segure o espectador
   ("mas o que aconteceu depois nao e o que voce espera...").
6. LOOP: a ultima fala deve retomar a primeira, fechando o ciclo e estimulando
   o rewatch.
7. CTA: somente no ultimo bloco. Nunca no comeco.
8. DURACAO: some as duracoes dos blocos ate chegar perto da duracao alvo
   informada, com tolerancia de 10 por cento.
9. Zero enrolacao, zero cliche de "nao pule", zero metafora confusa.

FORMATO DE SAIDA — responda SOMENTE com JSON valido, sem markdown e sem
explicacao:

{
  "titulo": "titulo magnetico, ate 60 caracteres",
  "thumbnail_text": "no maximo 4 palavras de impacto",
  "blocos": [
    {
      "tipo": "hook|promessa|giro|prova|cliffhanger|cta",
      "fala": "frase curta falada em pt-BR",
      "sugestao_visual": "o que mostrar na tela nesse bloco",
      "duracao_segundos": 3.0
    }
  ]
}

O primeiro bloco DEVE ser do tipo "hook" e o ultimo do tipo "cta".`;

export interface OpcoesRoteiro {
  tema: string;
  publico: string;
  duracaoSegundos: number;
  formato: string;
  tom: string;
}

export function montarPrompt(o: OpcoesRoteiro): string {
  return (
    `Tema: ${o.tema}\n` +
    `Publico: ${o.publico}\n` +
    `Formato: ${o.formato} (shorts = vertical 1080x1920, square = 1080x1080, standard = horizontal 1920x1080)\n` +
    `Duracao alvo: ${Math.round(o.duracaoSegundos)} segundos\n` +
    `Tom: ${o.tom}\n` +
    "Escreva o roteiro agora."
  );
}

export function extrairJson(textoBruto: string): Record<string, any> {
  let texto = textoBruto.trim();
  texto = texto.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  const inicio = texto.indexOf("{");
  const fim = texto.lastIndexOf("}");
  if (inicio < 0 || fim <= inicio) {
    throw new Error("O modelo nao retornou um JSON valido.");
  }
  try {
    return JSON.parse(texto.slice(inicio, fim + 1));
  } catch (err) {
    throw new Error(`Nao foi possivel interpretar o JSON do modelo: ${String(err)}`);
  }
}

export interface Bloco {
  tipo: TipoBloco;
  fala: string;
  sugestao_visual: string;
  duracao_segundos: number;
}

export interface RoteiroNormalizado {
  titulo: string;
  thumbnail_text: string;
  formato: string;
  duracao_estimada_segundos: number;
  sec_per_block: number;
  blocos: Bloco[];
  roteiro_texto: string;
  roteiro_json: Record<string, any>;
}

export function normalizar(
  dados: Record<string, any>,
  duracaoAlvo: number,
  formato: string,
  provedor: string,
  modelo: string,
): RoteiroNormalizado {
  const brutos: any[] = Array.isArray(dados.blocos) ? dados.blocos : [];
  if (!brutos.length) throw new Error("O modelo retornou um roteiro sem blocos.");

  const duracaoPadrao = Math.max(2, duracaoAlvo / brutos.length);
  const blocos: Bloco[] = [];

  for (const item of brutos) {
    if (!item || typeof item !== "object") continue;
    const fala = String(item.fala ?? "").trim();
    if (!fala) continue;
    let tipo = String(item.tipo ?? "giro").trim().toLowerCase() as TipoBloco;
    if (!(TIPOS_BLOCO as readonly string[]).includes(tipo)) tipo = "giro";
    let duracao = Number(item.duracao_segundos) || 0;
    if (!(duracao > 0)) duracao = duracaoPadrao;
    blocos.push({
      tipo,
      fala,
      sugestao_visual: String(item.sugestao_visual ?? "").trim(),
      duracao_segundos: Math.round(duracao * 100) / 100,
    });
  }

  if (!blocos.length) throw new Error("O modelo retornou blocos sem falas.");
  blocos[0].tipo = "hook";
  blocos[blocos.length - 1].tipo = "cta";

  const duracaoTotal = Math.round(blocos.reduce((s, b) => s + b.duracao_segundos, 0) * 100) / 100;
  const titulo = String(dados.titulo ?? "").trim() || "Roteiro NatoDark";
  const thumbnail = String(dados.thumbnail_text ?? "").trim();

  const roteiroJson = {
    titulo,
    thumbnail_text: thumbnail,
    formato,
    duracao_estimada_segundos: duracaoTotal,
    sec_per_block: Math.round((duracaoTotal / blocos.length) * 100) / 100,
    blocos,
  };

  return {
    ...roteiroJson,
    roteiro_texto: blocos.map((b) => b.fala).join("\n"),
    roteiro_json: { ...roteiroJson, modo: provedor, modelo },
  };
}
