from fastapi import FastAPI

app = FastAPI(title="MT5 Control Center API", version="0.1.0")

@app.get("/")
def root():
    return {"name": "MT5 Control Center", "status": "online", "version": "0.1.0"}

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "api", "mt5": "bridge-not-connected"}
