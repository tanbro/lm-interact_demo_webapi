from .app import app

from .views import chat

@app.get("/")
def root():
    return {"message": "Hello World"}
