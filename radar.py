from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import requests
import re

app = FastAPI(
    title="Radar do Caçador",
    description="Sistema que lê URLs do Mercado Livre, busca detalhes e monta posts convertivos.",
    version="2.0.0"
)

URLS_FILE = "urls.txt"
ML_ITEM_URL = "https://api.mercadolibre.com/items/{item_id}"

FATIAS_TURNO = {
    "manha": (0, 3),
    "tarde": (3, 6),
    "noite": (6, 9)
}

# ============================
# MODELOS
# ============================

class Produto:
    def __init__(self, nome, preco, preco_original, cupom, url):
        self.nome = nome
        self.preco = preco
        self.preco_original = preco_original
        self.cupom = cupom
        self.url = url


# ============================
# FUNÇÕES DE FORMATAÇÃO
# ============================

def formatar_preco(valor):
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def formatar_post(produto, indice):
    texto = f"🟡 Oferta {indice}\n\n"
    texto += f"{produto.nome}\n\n"

    # Preço original caso exista
    if produto.preco_original and produto.preco_original > produto.preco:
        texto += f"💸 De {formatar_preco(produto.preco_original)} → Por {formatar_preco(produto.preco)}\n\n"
    else:
        texto += f"💸 Por {formatar_preco(produto.preco)}\n\n"

    # Cupom — se existir
    if produto.cupom:
        texto += f"🎟️ Cupom: {produto.cupom}\n\n"

    # Link
    texto += "🔗 Link:\n"
    texto += f"{produto.url}\n\n"

    texto += "⚠️ Preço pode mudar a qualquer momento."

    return texto


# ============================
# FUNÇÃO PARA BUSCAR PRODUTO
# ============================

def obter_item_id(url):
    ids = re.findall(r"(MLB\\d+)", url)
    if not ids:
        return None
    return max(ids, key=len)


def buscar_produto(url):
    item_id = obter_item_id(url)
    if not item_id:
        return None

    api_url = ML_ITEM_URL.format(item_id=item_id)
    r = requests.get(api_url)

    if r.status_code != 200:
        return None

    data = r.json()

    nome = data.get("title", "Produto sem nome")
    preco = data.get("price", 0.0)
    preco_original = data.get("original_price", preco)
    cupom = data.get("deal_ids", None)  # alguns itens carregam cupons aqui
    link = data.get("permalink", url)

    return Produto(nome, preco, preco_original, cupom, link)


# ============================
# LEITURA DE URLs
# ============================

def carregar_urls():
    try:
        with open(URLS_FILE, "r") as f:
            urls = [linha.strip() for linha in f.readlines() if linha.strip()]
        return urls
    except:
        return []


# ============================
# ROTAS
# ============================

@app.get("/", response_class=PlainTextResponse)
def raiz():
    return "Radar do Caçador online! ⚡"


@app.get("/teste", response_class=PlainTextResponse)
def teste():
    return "Rota de teste OK!"


@app.get("/pacote/{turno}", response_class=PlainTextResponse)
def gerar_pacote(turno: str):

    turno = turno.lower()
    if turno not in FATIAS_TURNO:
        return "❌ Turno inválido. Use: manha, tarde, noite."

    urls = carregar_urls()
    if not urls:
        return (
            f"⚡ Pacote — {turno} — Caçador de Ofertas\n\n"
            "Não há produtos cadastrados em urls.txt no momento.\n"
            "Adicione algumas URLs e tente novamente."
        )

    inicio, fim = FATIAS_TURNO[turno]
    urls_turno = urls[inicio:fim]

    linhas = [f"⚡ Pacote — {turno} — Caçador de Ofertas\n"]

    if not urls_turno:
        linhas.append("Nenhum produto disponível para este turno.")
        return "\n".join(linhas)

    for i, url in enumerate(urls_turno, start=1):
        produto = buscar_produto(url)

        if not produto:
            linhas.append(f"❌ Erro ao buscar dados do produto {i}")
            continue

        post = formatar_post(produto, i)
        linhas.append(post)
        linhas.append("")

    return "\n".join(linhas)
