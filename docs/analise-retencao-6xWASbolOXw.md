# Análise de modelo — vídeo de mistério de alta retenção

**Vídeo:** https://www.youtube.com/watch?v=6xWASbolOXw
**Canal:** Fabiano - Histórias Sobrenaturais
**Publicado:** 14/11/2026 · **Duração:** 16:56 · **Formato:** horizontal 16:9

> Escopo: análise do **triângulo do clique** (título, thumbnail, abertura) e do
> padrão narrativo. **Não** é auditoria de retenção: não houve acesso ao gráfico
> de retenção nem a um vídeo "vencedor" do mesmo canal para servir de baseline.
> Os números de retenção relatados pelo usuário foram tratados como contexto,
> não like medição.

## Dados observáveis

| Item | Valor |
|---|---|
| Título | UM CAMINHONEIRO PAROU PARA JANTAR NUM RESTAURANTE E DESCOBRIU ALGO ATERRORIZANTE |
| Descrição (abertura) | 🚛👻 1964 — O MISTÉRIO DO RESTAURANTE BOA VIAGEM! Durante uma viagem pela madrugada, um caminhoneiro faminto encontrou um pequeno restaurante iluminado à beira... |
| Thumbnail | `maxresdefault.jpg` 1280×720 |
| Comentário em destaque | Filho de caminhoneiro relata histórias do pai nas estradas do Brasil · 61 curtidas |

## O que esse vídeo faz de certo (e que copiamos)

1. **Persona comum + ação banal + descoberta extrema.**
   "Caminhoneiro" + "parou para jantar" + "algo aterrorizante". O espectador se
   vê na cena antes de saber o mistério. É a promessa do título inteira em 12
   palavras.

2. **Âncora concreta antes da pergunta.**
   A descrição abre com `1964` e `Restaurante Boa Viagem`. Ano + lugar nomeado
   transformam "história de terror" em "caso". Credibilidade imediata, zero
   enrolação.

3. **Curiosidade distribuída, não despejada.**
   O título promete a descoberta, mas não diz qual. A descrição dá o cenário e
   para no "iluminado à beira...". O cérebro completa a imagem e fica pendente.

4. **Espelho emocional no comentário fixado.**
   Um relato de terceiro ("meu pai era caminhoneiro...") funciona como prova
   social e aumenta o tempo de permanência na área de comentários nos primeiros
   minutos — sinal forte para o algoritmo.

5. **Simplicidade como vantagem.**
   É uma história narrada com poucos elementos visuais. O orçamento vai para
   atmosfera/voz, não para stock caro. Isso confirma: **roteiro bom > edição
   cara**. Nosso `media_scout` já entende isso ao alternar vídeo/imagem por
   bloco em vez de empilhar efeitos.

6. **Formato longo com ritmo curto.**
   16:56 funciona porque o mistério é reaberto em ciclos: cada resposta abre
   uma pergunta menor. É exatamente o "pattern interrupt a cada 5–8s" que já
   está no nosso prompt.

## Aplicação no NatoDark (já aplicada)

Adicionamos duas regras ao `SYSTEM_PROMPT` — no backend Python e no Worker —
para reproduzir esse padrão:

- **Regra 10 (Âncora):** o primeiro bloco cita ano, lugar, objeto ou profissão
  antes da pergunta.
- **Regra 11 (Título):** persona comum + ação cotidiana + descoberta
  impactante, no molde do vídeo analisado.

Elas convivem com as regras já existentes de hook no segundo 0, curiosidade
distribuída, cliffhanger antes da virada, loop final e CTA só no último bloco.

## O que NÃO copiar

- **Não usar o vídeo como matéria-prima.** Usar clipes do canal alheio é risco
  de Content ID; crédito e "transformação" não protegem automaticamente. O
  vídeo aqui serve só como referência de formato.
- **Não imitar o título com `CAPS LOCK` integral** em todos os vídeos: funciona
  nesse nicho, mas cansatiza se virar fórmula única. Alterne com títulos de
  pergunta e de contradição.
- **Não confundir "simples" com "canhestre":** a simplicidade aqui é edição
  enxuta com informação densa, não áudio ruim nem fala arrastada.

## Para uma auditoria completa de verdade

Falta o **gráfico de retenção** (print do YouTube Studio) e, idealmente, o
gráfico de um vídeo vencedor do mesmo canal. Com isso, dá para marcar as quedas
por zona (cliff 0–30s, intro, body, sag ~40–60%, end) e mapear cada dip para o
bloco do roteiro que estava no ar. Sem isso, qualquer número de retenção seria
invenção.
