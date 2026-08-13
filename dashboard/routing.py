from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('ws/canli/', consumers.CanliGuncellemeConsumer.as_asgi()),
]
