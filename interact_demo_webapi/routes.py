from .app import app
from .views import hello, chat, qa


app.add_route(hello.hello, '/hello')

app.add_route(chat.Index.as_view(), '/chat')
app.add_route(chat.Index.as_view(), '/chat/<id_:int>')
app.add_route(chat.Input.as_view(), '/chat/<id_:int>/input')
app.add_route(chat.Clear.as_view(), '/chat/<id_:int>/clear')

app.add_route(qa.Index.as_view(), '/qa')
