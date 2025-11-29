from client.lib import AbstractEventHandler, register, BaseAPI

class BaseUsbipEventHandler(AbstractEventHandler):
    @register("export", "serial", "busid", "server_ip", "usbip_port")
    def export(self, serial, busid, server_ip, usbip_port):
        pass

    @register("disconnect", "serial")
    def disconnect(self, serial):
        pass

class UsbipAPI(BaseAPI):
    def reserve(self, amount, subscription_url):
        return super().reserve(amount, subscription_url, "usbip", {})

    def unbind(self, serial):
        return self.requestWorker(serial, "/request", {
            "serial": serial,
            "event": "unbind"
        })
