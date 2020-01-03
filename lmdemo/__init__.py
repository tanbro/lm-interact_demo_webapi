from .app import app
from .views import chat, qa


@app.get("/")
def root():
    return {"message": "Hello World"}
