from datetime import date
from typing import List, Dict
from urllib.parse import urlparse
import random

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI(
    title="Radar do Caçador",
    description="Lê uma lista de URLs do Mercado Livre e monta pacotes de posts.",
    version="1.0.0",
)

# ==========================
# CONFIGURAÇÕES
# ==========================

URLS_FILE = "urls.txt"

# índices de fatia por turno (3 produtos por pacote)
FATIAS_TURNO: Dict[str, range] = {
    "manha": range(0, 3),   # produtos 0,1,2
    "tarde": range(3, 6),   # produtos 3,4,5
    "noite": range(6, 9),   # produtos 6,7,8
}


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
        urls = [l for l in linhas if l]
        if not urls:
            raise HTTPException(
                status_code=500,
                detail="urls.txt está vazio. Adicione algumas URLs de produtos."
            )
        return urls
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Arquivo urls.txt não encontrado no servidor."
        )


def extrair_nome_do_slug(url: str) -> str:
    """
    A partir da URL do Mercado Livre, tenta extrair o 'slug' do produto
    e transformá-lo em um nome legível.
    Exemplo:
    .../creatina-monohidratada-500g-soldiers-nutrition-100-pura.../p/MLB123
    -> 'Creatina Monohidratada 500g Soldiers Nutrition 100 Pura'
    """
    caminho = urlparse(url).path  # /creatina-monohidratada.../p/MLB...
    # pega a parte antes de /p/
    parte_produto = caminho.split("/p/")[0]
    # pega o último segmento depois da barra
    slug = parte_produto.strip("/").split("/")[-1]
    # troca hífens por espaço
    nome_bruto = slug.replace("-", " ")
    # capitaliza cada palavra
    nome_formatado = " ".join(p.capitalize() for p in nome_bruto.split())
    return nome_formatado or "Oferta especial"


def selecionar_urls_para_turno(urls: List[str], turno: str) -> List[str]:
    """
    Rotaciona / embaralha a lista de URLs com base na data + turno
    e pega 3 diferentes para cada período.
    """
    if turno not in FATIAS_TURNO:
        raise HTTPException(status_code=400, detail=f"Turno inválido: {turno}")

    if not urls:
        return []

    hoje = date.today().isoformat()
    seed = f"{hoje}-{turno}"
    rnd = random.Random(seed)
    urls_embaralhadas = urls[:]  # cópia
    rnd.shuffle(urls_embaralhadas)

    faixa = FATIAS_TURNO[turno]
    selecionadas: List[str] = []

    for idx in faixa:
        if idx < len(urls_embaralhadas):
            selecionadas.append(urls_embaralhadas[idx])

    return selecionadas


def montar_texto_pacote(turno: str, urls: List[str]) -> str:
    linhas: List[str] = []

    titulo_mapa = {
        "manha": "Pacote das 6h",
        "tarde": "Pacote das 12h",
        "noite": "Pacote das 19h",
    }
    titulo = titulo_mapa.get(turno, f"Pacote — {turno}")

    linhas.append(f"⚡ {titulo} — Caçador de Ofertas\n")

    if not urls:
        linhas.append("Hoje não encontrei URLs cadastradas para esse horário. 😅")
        linhas.append("Atualize o arquivo urls.txt e tente novamente.\n")
    else:
        for i, url in enumerate(urls, start=1):
            nome = extrair_nome_do_slug(url)
            linhas.append(f"🟡 Oferta {i}")
            linhas.append(nome)
            linhas.append(f"🔗 {url}")
            linhas.append("")  # linha em branco

    linhas.append("💬 Eu caço e você economiza.")
    linhas.append("⚠️ Preços e estoque podem mudar a qualquer momento.\n")

    return "\n".join(linhas)


def gerar_pacote(turno: str) -> str:
    urls = carregar_urls()
    selecionadas = selecionar_urls_para_turno(urls, turno)
    texto = montar_texto_pacote(turno, selecionadas)
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
    turno = turno.lower()
    texto = gerar_pacote(turno)
    return texto
