from .app import app
from .views import hello, interact


app.add_route(hello.hello, '/hello')
app.add_route(interact.Index.as_view(), '/interact')
app.add_route(interact.Index.as_view(), '/interact/<id_:int>')
app.add_route(interact.Input.as_view(), '/interact/<id_:int>/input')
app.add_route(interact.Clear.as_view(), '/interact/<id_:int>/clear')
