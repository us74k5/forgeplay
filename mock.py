from fastapi import FastAPI

app = FastAPI()

@app.post("/download")
def download():
    return {"playerUrl": "https://example.com"}