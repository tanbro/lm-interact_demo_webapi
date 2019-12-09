from .app import app
from .views import hello, interact


app.add_route(hello.hello, '/hello')
app.add_route(interact.List.as_view(), '/interact')
app.add_route(interact.Detail.as_view(), '/interact/<id_:int>')
app.add_route(interact.Reset.as_view(), '/interact/reset')
app.add_route(interact.Input.as_view(), '/interact/<id_:int>/input')
