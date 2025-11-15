from client.ControlAPI import ControlAPI
from client.DeviceUtils import DeviceUtils
from client.EventServer import EventServer
from utils.utils import get_ip

class Client(ControlAPI, DeviceUtils):
    def __init__(self, clientname, control_server_url, logger):
        super().__init__(control_server_url, clientname, logger)
        self.logger = logger

        # serial -> (ip, port)
        self.serial_locations = {}

        self.clientname = clientname
        self.event_server = None

    def startEventServer(self, eventhandlers, ip=get_ip(), port=8080):
        self.event_server = EventServer(self, eventhandlers, self.logger)
        self.event_server.start(self, ip, port)
    
    def stopEventServer(self):
        if self.event_server:
            self.event_server.stop()

    def reserve(self, amount):
        """Reserves and connects to the specified amount of devices and returns their serials.
        If there are not enough devices available, it will reserve as many as it can."""
        if not self.event_server:
            raise Exception("event server not started")

        data = super().reserve(amount, self.event_server.getUrl())

        if not data:
            return False
        
        serials = []

        for row in data:
            self.serial_locations[row["serial"]] = (row["ip"], row["usbipport"])
            self.event_server.triggerExport(row["serial"], row["bus"], row["ip"], row["usbipport"])
            serials.append(row["serial"])
        
        return serials
    
    def getConnectionInfo(self, serial):
        """Returns (ip, port) needed to connect to serial, or None."""
        return self.serial_locations.get(serial)
    
    def triggerTimeout(self, serial):
        """Triggers a timeout event on the event server. This is used by the TimeoutDetector"""
        conninfo = self.serial_locations.get(serial)

        if not conninfo:
            self.logger.error(f"device {serial} timed out but no connection information")
        
        ip, port = conninfo

        self.event_server.triggerTimeout(serial, ip, port)
