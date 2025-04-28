class LSIS_Framer:
    def __init__(self, decoder, client=None):
        self.decoder = decoder
        self.client = client

    def sendPacket(self, message):
        return self.client.send(message)

    def recvPacket(self, size):
        return self.client.recv(size)
