from dataclasses import dataclass
from typing import List, Dict
import requests

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="Radar do Caçador",
    description="Backend simples para buscar ofertas no Mercado Livre e formatar pacotes de posts.",
    version="0.1.0",
)

# ==========================
# CONFIGURAÇÕES BÁSICAS
# ==========================

MELI_SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"

# Palavras-chave por turno (ajuste como quiser)
KEYWORDS_BY_TURNO: Dict[str, List[str]] = {
    "manha": ["fone bluetooth", "headset gamer"],
    "tarde": ["lanterna tática", "kit ferramenta"],
    "noite": ["suporte veicular", "gadget automotivo", "carregador veicular"],
}

# Preço máximo (troque ou coloque None se não quiser limite)
PRECO_MAXIMO = 250.0


@dataclass
class Produto:
    nome: str
    preco: float
    link: str
    frete_gratis: bool
    vendas: int = 0  # sold_quantity
    score: float = 0  # usado para ordenar


# ==========================
# FUNÇÕES DE NEGÓCIO
# ==========================

def buscar_produtos_meli(termo: str, limite: int = 30) -> List[dict]:
    """
    Chama a API pública de busca do Mercado Livre para um termo.
    """
    params = {
        "q": termo,
        "limit": limite,
        "sort": "sold_quantity_desc",  # tenta priorizar mais vendidos
    }

    resp = requests.get(MELI_SEARCH_URL, params=params, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Erro ao chamar Mercado Livre: {resp.text}")

    data = resp.json()
    return data.get("results", [])


def converter_para_produtos(brutos: List[dict]) -> List[Produto]:
    produtos: List[Produto] = []

    for item in brutos:
        try:
            nome = item.get("title") or "Produto sem título"
            preco = float(item.get("price") or 0)

            if preco <= 0:
                continue

            if PRECO_MAXIMO is not None and preco > PRECO_MAXIMO:
                continue

            link = item.get("permalink") or ""
            if not link:
                continue

            shipping = item.get("shipping", {}) or {}
            frete_gratis = bool(shipping.get("free_shipping", False))

            # se quiser permitir sem frete grátis, comente o bloco abaixo:
            if not frete_gratis:
                continue

            vendas = int(item.get("sold_quantity") or 0)

            # score simples: prioriza quem mais vendeu
            score = float(vendas)

            produtos.append(
                Produto(
                    nome=nome,
                    preco=preco,
                    link=link,
                    frete_gratis=frete_gratis,
                    vendas=vendas,
                    score=score,
                )
            )
        except Exception:
            # Ignora itens quebrados
            continue

    return produtos


def selecionar_top_n(produtos: List[Produto], n: int = 3) -> List[Produto]:
    ordenados = sorted(produtos, key=lambda p: p.score, reverse=True)
    return ordenados[:n]


def formatar_preco_brl(valor: float) -> str:
    """
    Formata o preço no padrão brasileiro: R$ 1.234,56
    """
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def montar_texto_pacote(turno: str, produtos: List[Produto]) -> str:
    linhas: List[str] = []
    titulo_mapa = {
        "manha": "Pacote das 6h",
        "tarde": "Pacote das 12h",
        "noite": "Pacote das 19h",
    }
    titulo = titulo_mapa.get(turno, f"Pacote — {turno}")

    linhas.append(f"⚡ {titulo} — Caçador de Ofertas\n")

    if not produtos:
        linhas.append("Hoje não encontrei produtos bons o suficiente para esse horário. 😅")
        linhas.append("Amanhã o radar tenta de novo.\n")
    else:
        for p in produtos:
            linhas.append(p.nome)
            linhas.append("")
            linhas.append(formatar_preco_brl(p.preco))
            linhas.append("Cupom: —")  # depois podemos integrar com cupons, se tiver
            linhas.append(f"Link: {p.link}")
            linhas.append("")  # linha em branco entre os produtos

    linhas.append("💬 Eu caço e você economiza.")
    linhas.append("⚠️ Preços e estoque podem mudar a qualquer momento.\n")

    return "\n".join(linhas)


def gerar_pacote(turno: str) -> str:
    turno = turno.lower()
    if turno not in KEYWORDS_BY_TURNO:
        raise HTTPException(status_code=400, detail=f"Turno inválido: {turno}")

    termos = KEYWORDS_BY_TURNO[turno]

    todos_brutos: List[dict] = []
    for termo in termos:
        try:
            resultados = buscar_produtos_meli(termo)
            todos_brutos.extend(resultados)
        except HTTPException:
            # apenas segue para o próximo termo se uma busca falhar
            continue

    produtos = converter_para_produtos(todos_brutos)
    top3 = selecionar_top_n(produtos, n=3)
    texto = montar_texto_pacote(turno, top3)
    return texto


# ==========================
# ROTAS DA API
# ==========================

@app.get("/", response_class=PlainTextResponse)
def raiz():
    return (
        "Radar do Caçador online ⚡\n"
        "Use /pacote/manha, /pacote/tarde ou /pacote/noite para gerar seus posts."
    )


@app.get("/pacote/{turno}", response_class=PlainTextResponse)
def obter_pacote(turno: str):
    """
    Exemplos: /pacote/manha  /pacote/tarde  /pacote/noite
    """
    texto = gerar_pacote(turno)
    return texto
