from dataclasses import dataclass
from typing import List, Dict
import re
import requests
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="Radar do Caçador",
    description="Lê uma lista de URLs do Mercado Livre, busca detalhes dos produtos e monta pacotes de posts.",
    version="1.0.0",
)

# ==========================
# CONFIGURAÇÕES
# ==========================

URLS_FILE = "urls.txt"  # arquivo com 1 URL por linha
MELI_ITEM_URL = "https://api.mercadolibre.com/items/{item_id}"

# índices de fatia por turno (3 produtos por pacote)
FATIAS_TURNO: Dict[str, range] = {
    "manha": range(0, 3),   # produtos 0,1,2
    "tarde": range(3, 6),   # produtos 3,4,5
    "noite": range(6, 9),   # produtos 6,7,8
}


@dataclass
class Produto:
    nome: str
    preco: float
    link: str
    vendas: int = 0  # sold_quantity
    id_item: str = ""


# ==========================
# FUNÇÕES AUXILIARES
# ==========================

def carregar_urls() -> List[str]:
    """
    Lê o arquivo urls.txt e retorna a lista de URLs (sem linhas vazias).
    """
    try:
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            linhas = [l.strip() for l in f.readlines()]
        return [l for l in linhas if l]
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Arquivo urls.txt não encontrado no servidor.")


def extrair_id_item(url: str) -> str:
    """
    Extrai o ID mais relevante de um produto na URL.
    Em URLs com vários MLBs, pegamos o MAIOR (que é o ID do anúncio).
    """
    matches = re.findall(r"(MLB\d+)", url)
    if not matches:
        raise ValueError(f"Não foi possível extrair ID MLB da URL: {url}")

    # Pegamos o número mais longo (ID do anúncio)
    return max(matches, key=len)


def buscar_detalhes_produto(item_id: str) -> Produto:
    """
    Chama a API pública de detalhes de item do Mercado Livre e
    retorna um objeto Produto.
    """
    url = MELI_ITEM_URL.format(item_id=item_id)
    resp = requests.get(url, timeout=10)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao buscar item {item_id} no Mercado Livre: {resp.text}",
        )

    data = resp.json()

    nome = data.get("title") or f"Produto {item_id}"
    preco = float(data.get("price") or 0)
    link = data.get("permalink") or ""
    vendas = int(data.get("sold_quantity") or 0)

    return Produto(
        nome=nome,
        preco=preco,
        link=link,
        vendas=vendas,
        id_item=item_id,
    )


def formatar_preco_brl(valor: float) -> str:
    """
    Formata o preço no padrão brasileiro: R$ 1.234,56
    """
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def carregar_produtos() -> List[Produto]:
    """
    Lê o urls.txt, busca detalhes de cada produto e devolve uma lista
    ordenada dos mais vendidos para os menos vendidos.
    """
    urls = carregar_urls()

    produtos: List[Produto] = []
    for url in urls:
        try:
            item_id = extrair_id_item(url)
            produto = buscar_detalhes_produto(item_id)
            produtos.append(produto)
        except Exception:
            # Se der problema em um item, simplesmente pula
            continue

    # ordena por vendas (mais vendidos primeiro)
    produtos.sort(key=lambda p: p.vendas, reverse=True)
    return produtos


def selecionar_produtos_para_turno(produtos: List[Produto], turno: str) -> List[Produto]:
    """
    Usa a data do dia para criar um "embaralhamento" estável
    e fatia a lista para cada turno, sem repetir entre manhã/tarde/noite.
    """
    if turno not in FATIAS_TURNO:
        raise HTTPException(status_code=400, detail=f"Turno inválido: {turno}")

    # embaralhamento simples baseado na data (mesmo resultado dentro do dia)
    hoje = date.today().toordinal()
    # rotação da lista: desloca de acordo com o dia
    deslocamento = hoje % len(produtos) if produtos else 0
    produtos_rotacionados = produtos[deslocamento:] + produtos[:deslocamento]

    faixa = FATIAS_TURNO[turno]
    selecionados = []

    for idx in faixa:
        if idx < len(produtos_rotacionados):
            selecionados.append(produtos_rotacionados[idx])

    return selecionados


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
            linhas.append("Cupom: —")  # se um dia tiver cupom, a gente pluga aqui
            linhas.append(f"Link: {p.link}")
            linhas.append("")  # linha em branco entre produtos

    linhas.append("💬 Eu caço e você economiza.")
    linhas.append("⚠️ Preços e estoque podem mudar a qualquer momento.\n")

    return "\n".join(linhas)


def gerar_pacote(turno: str) -> str:
    produtos = carregar_produtos()
    if not produtos:
        return (
            f"⚡ Pacote — {turno} — Caçador de Ofertas\n\n"
            "Não há produtos cadastrados em urls.txt no momento.\n"
            "Adicione algumas URLs de produtos do Mercado Livre e tente novamente.\n"
        )

    selecionados = selecionar_produtos_para_turno(produtos, turno)
    texto = montar_texto_pacote(turno, selecionados)
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
    turno = turno.lower()
    texto = gerar_pacote(turno)
    return texto
