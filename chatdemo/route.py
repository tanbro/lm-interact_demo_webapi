from .app import app
from .views import HelloRootView


def setup_routings():
    app.add_route(HelloRootView.as_view(), '/')
