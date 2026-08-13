"""
ASGI config for afetos project.

HTTP istekleri Django'nun kendi ASGI handler'ına, WebSocket istekleri ise
channels üzerinden dashboard/routing.py'deki consumer'a yönlendirilir.
Canlı güncelleme SADECE dashboard (ana panel) ve harita sayfalarında
kullanılıyor — bkz. dashboard/consumers.py, dashboard/realtime.py.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afetos.settings')

# get_asgi_application() Django app registry'sini hazırlar; websocket
# routing'i import eden modüller (dolayısıyla Django modelleri) bundan
# SONRA import edilmeli.
django_asgi_app = get_asgi_application()

from dashboard.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
