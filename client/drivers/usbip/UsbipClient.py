from client.lib import EventServer
from client.drivers.usbip import UsbipHandler
from client.base.usbip import UsbipAPI
from client.util import DefaultEventHandler

class UsbipClient(UsbipAPI):
    def __init__(self, control_url, client_name, logger):
        super().__init__(control_url, client_name, logger)

        self.server = EventServer(logger)

        default = DefaultEventHandler(self.server, self, logger)
        usbip = UsbipHandler(self.server, self, logger)

        self.eh = [default, usbip]

    def start(self, client_ip: str, client_port: str):
        self.server.start(client_ip, client_port, self.eh)

    def stop(self):
        self.server.stop()
