"""
Catalogo de agentes de IA do NatoDark Studio.

Cada modelo ganha um "agente" com nome e sobrenome de zueira, de acordo com o
servico que ele faz melhor. A ideia e deixar claro no painel quem esta trabalhando
e quem e reserva — sem nunca expor chaves.

Este modulo NAO faz chamadas de rede. Ele so reorganiza informacao e pontua
cada modelo por funcao. O teste real de saude fica em llm_router.testar_modelo().
"""

from typing import Any, Dict, List, Optional

# Servicos usados na producao de um video de YouTube.
SERVICOS: Dict[str, str] = {
    "roteiro": "Estrutura o roteiro: hook, curiosidade, pattern interrupt, cliffhanger, loop e CTA.",
    "titulos": "Cria titulos e ganchos de alta retencao (curiosidade + promessa).",
    "hype": "Analisa tendencias, comentarios e angulos virais antes de escrever.",
    "legendas": "Revisa e ajusta falas para legenda falada em pt-BR.",
    "revisao": "Rele o texto, corta enrolled e corrige ritmo/ortografia.",
    "reserva": "Fallback: entra quando o titular falha ou esta sem cota.",
}

# Nomes por servico. Sempre nome + sobrenome, para identificar no log/painel.
AGENTES: Dict[str, Dict[str, str]] = {
    "roteiro": {"nome": "Dr. Gancho", "sobrenome": "da Silva Corte Seco"},
    "titulos": {"nome": "Capitao Clickbait", "sobrenome": "Pereira"},
    "hype": {"nome": "Dona Curiosidade", "sobrenome": "AlmeidaTrend"},
    "legendas": {"nome": "Zé Legendinha", "sobrenome": "Santos"},
    "revisao": {"nome": "Prof. Pattern Interrupt", "sobrenome": "Gomes"},
    "reserva": {"nome": "Tio fallback", "sobrenome": "Ribeiro"},
}

# Pontuacao empirica por familia de modelo. Naoprova que o modelo e bom —
# apenas ordena quem testar primeiro em cada funcao. O teste real decide.
PONTOS: Dict[str, Dict[str, int]] = {
    "gemini": {"roteiro": 5, "titulos": 5, "hype": 4, "legendas": 4, "revisao": 5, "reserva": 5},
    "nvidia": {"roteiro": 4, "titulos": 4, "hype": 3, "legendas": 4, "revisao": 4, "reserva": 5},
    "groq": {"roteiro": 4, "titulos": 5, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 4},
    "openrouter": {"roteiro": 4, "titulos": 4, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 4},
    "cloudflare": {"roteiro": 3, "titulos": 3, "hype": 3, "legendas": 3, "revisao": 3, "reserva": 4},
    "openai": {"roteiro": 4, "titulos": 4, "hype": 4, "legendas": 5, "revisao": 5, "reserva": 3},
    "anthropic": {"roteiro": 5, "titulos": 4, "hype": 4, "legendas": 5, "revisao": 5, "reserva": 3},
    "ollama": {"roteiro": 3, "titulos": 3, "hype": 2, "legendas": 3, "revisao": 3, "reserva": 4},
    "kilocode": {"roteiro": 4, "titulos": 4, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 5},
    "llm7": {"roteiro": 3, "titulos": 3, "hype": 2, "legendas": 3, "revisao": 3, "reserva": 4},
    "aionlabs": {"roteiro": 5, "titulos": 4, "hype": 3, "legendas": 4, "revisao": 4, "reserva": 3},
    "axforge": {"roteiro": 4, "titulos": 3, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 4},
    "zai": {"roteiro": 4, "titulos": 4, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 4},
    "gonka": {"roteiro": 4, "titulos": 3, "hype": 3, "legendas": 3, "revisao": 4, "reserva": 3},
    "modelscope": {"roteiro": 3, "titulos": 3, "hype": 2, "legendas": 3, "revisao": 3, "reserva": 3},
    "siliconflow": {"roteiro": 3, "titulos": 3, "hype": 2, "legendas": 4, "revisao": 3, "reserva": 3},
    "ovh": {"roteiro": 3, "titulos": 3, "hype": 2, "legendas": 3, "revisao": 3, "reserva": 5},
    "cohere": {"roteiro": 3, "titulos": 3, "hype": 3, "legendas": 4, "revisao": 3, "reserva": 2},
}

# Modelos candidatos por provedor. "servicos" = onde ele e indicado.
# Todos sao modelos de texto; visao/audio ficam fora do router.
CANDIDATOS: List[Dict[str, Any]] = [
    # Google Gemini — tier gratuito generoso, bom padrao para roteiro.
    {"provider": "gemini", "modelo": "gemini-2.5-flash", "servicos": ["roteiro", "titulos", "revisao"]},
    {"provider": "gemini", "modelo": "gemini-2.5-flash-lite", "servicos": ["titulos", "legendas", "reserva"]},
    # NVIDIA NIM — endpoints gratuitos, compativeis com OpenAI.
    {"provider": "nvidia", "modelo": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "servicos": ["roteiro", "revisao"]},
    {"provider": "nvidia", "modelo": "meta/llama-4-maverick-17b-128e-instruct", "servicos": ["roteiro", "titulos", "hype"]},
    {"provider": "nvidia", "modelo": "mistralai/mistral-large-3-675b-instruct-2512", "servicos": ["roteiro", "revisao"]},
    {"provider": "nvidia", "modelo": "qwen/qwen3-coder-480b-a35b-instruct", "servicos": ["revisao", "reserva"]},
    # Groq — muito rapido, otimo para titulos e testes.
    {"provider": "groq", "modelo": "llama-3.3-70b-versatile", "servicos": ["roteiro", "titulos", "reserva"]},
    {"provider": "groq", "modelo": "openai/gpt-oss-120b", "servicos": ["hype", "revisao"]},
    # OpenRouter — modelos :free.
    {"provider": "openrouter", "modelo": "meta-llama/llama-3.3-70b-instruct:free", "servicos": ["roteiro", "reserva"]},
    {"provider": "openrouter", "modelo": "google/gemma-3-27b-it:free", "servicos": ["titulos", "legendas"]},
    # Workers AI.
    {"provider": "cloudflare", "modelo": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "servicos": ["roteiro", "reserva"]},
    # Opcionais pagos.
    {"provider": "openai", "modelo": "gpt-4o-mini", "servicos": ["legendas", "revisao", "titulos"]},
    {"provider": "anthropic", "modelo": "claude-sonnet-4-5", "servicos": ["roteiro", "revisao"]},
    # Ollama (modelos locais que você instalou).
    {"provider": "ollama", "modelo": "llama3.1", "servicos": ["roteiro", "reserva"]},
    {"provider": "ollama", "modelo": "gemma3", "servicos": ["titulos", "legendas"]},
    {"provider": "ollama", "modelo": "qwen2.5", "servicos": ["revisao", "reserva"]},
    # awesome-free-llm-apis — aprovados em teste real, sem chave.
    {"provider": "kilocode", "modelo": "kilo-auto/free", "servicos": ["roteiro", "titulos", "reserva"]},
    {"provider": "llm7", "modelo": "gpt-oss:20b", "servicos": ["roteiro", "reserva"]},
    {"provider": "ovh", "modelo": "Meta-Llama-3_3-70B-Instruct", "servicos": ["reserva", "revisao"]},
    # awesome-free-llm-apis — precisam de chave; entram no router quando cadastradas.
    {"provider": "aionlabs", "modelo": "aion-labs/aion-3.0-mini", "servicos": ["roteiro", "titulos"]},
    {"provider": "axforge", "modelo": "glm-5.3-flash", "servicos": ["roteiro", "revisao"]},
    {"provider": "zai", "modelo": "glm-4.7-flash", "servicos": ["titulos", "revisao"]},
    {"provider": "gonka", "modelo": "deepseek-ai/DeepSeek-V4-Flash-0731", "servicos": ["roteiro", "hype"]},
    {"provider": "modelscope", "modelo": "Qwen/Qwen3.5-35B-A3B", "servicos": ["legendas", "reserva"]},
    {"provider": "siliconflow", "modelo": "tencent/Hunyuan-MT-7B", "servicos": ["legendas", "revisao"]},
    {"provider": "cohere", "modelo": "command-r-08-2024", "servicos": ["legendas"]},
]


def nome_agente(provider: str, servico: str = "reserva") -> str:
    """Devolve 'Nome Sobrenome' do agente para um provedor/servico."""
    dados = AGENTES.get(servico, AGENTES["reserva"])
    return f"{dados['nome']} {dados['sobrenome']}"


def pontuacao(provider: str, servico: str) -> int:
    return PONTOS.get(provider, {}).get(servico, 0)


def listar_agentes() -> List[Dict[str, Any]]:
    """Lista todos os agentes com servico e models candidatos, sem chaves."""
    saida: List[Dict[str, Any]] = []
    for servico, descricao in SERVICOS.items():
        titular = max(CANDIDATOS, key=lambda c: pontuacao(c["provider"], servico))
        candidatos = [
            dict(c, agente=nome_agente(c["provider"], servico), pontos=pontuacao(c["provider"], servico))
            for c in CANDIDATOS
            if servico in c["servicos"]
        ]
        candidatos.sort(key=lambda c: c["pontos"], reverse=True)
        saida.append({
            "servico": servico,
            "descricao": descricao,
            "agente": nome_agente(titular["provider"], servico),
            "titular_sugerido": {"provider": titular["provider"], "modelo": titular["modelo"]},
            "candidatos": candidatos,
        })
    return saida


def candidatos_provider(provider: Optional[str] = None) -> List[Dict[str, Any]]:
    """Candidatos de um provider (ou todos), ja com nome de agente."""
    itens = CANDIDATOS if not provider else [c for c in CANDIDATOS if c["provider"] == provider]
    return [
        dict(c, agente=nome_agente(c["provider"], c["servicos"][0]))
        for c in itens
    ]
