from .app import app


@app.get("/")
def root():
    return {"message": "Hello World"}
