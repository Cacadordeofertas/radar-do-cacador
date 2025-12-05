from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def raiz():
    return {"status": "Radar do Caçador online ⚡"}

@app.get("/teste")
def teste():
    return {"mensagem": "Rota de teste funcionando!"}
