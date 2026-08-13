from channels.generic.websocket import AsyncWebsocketConsumer


class CanliGuncellemeConsumer(AsyncWebsocketConsumer):
    """
    Tek bir yayın grubuna (afetos_canli) bağlanan basit bir WebSocket
    tüketicisi. İstemciden mesaj beklemiyoruz; sadece sunucudan istemciye
    tek yönlü güncelleme yayını yapıyoruz (dashboard + harita sayfaları).
    """

    GRUP_ADI = 'afetos_canli'

    async def connect(self):
        await self.channel_layer.group_add(self.GRUP_ADI, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GRUP_ADI, self.channel_name)

    async def guncelleme_gonder(self, event):
        """
        `channel_layer.group_send` ile {'type': 'guncelleme.gonder', ...}
        gönderildiğinde çağrılır (channels 'guncelleme.gonder' tipini bu
        metoda eşler). Gelen içeriği doğrudan istemciye iletir.
        """
        await self.send(text_data=event['icerik'])
