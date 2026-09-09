from fastapi import FastAPI

app = FastAPI(title="Demo FastAPI")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}
