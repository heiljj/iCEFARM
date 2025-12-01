import uuid
from usbipice.client.lib import AbstractEventHandler, register, BaseAPI

class PulseCountEventHandler(AbstractEventHandler):
    @register("serial", "results")
    def results(self, serial: str, results: dict[str, str]):
        """Called when ALL bitstreams have been evaluated. Results maps
        from the file parameter used in the request body to the 
        pulse amount."""

class PulseCountAPI(BaseAPI):
    def evaluate(self, serial: str, identifiers: list[uuid.UUID], bitstream_paths: list[str]):
        """Queues bitstreams for evaluations on device serial. Identifiers are used when 
        sending back the results - these should be unique and not reused."""

        files = {}
        for iden, path in zip(identifiers, bitstream_paths):
            files[iden] = open(path, "rb")

        res = self.requestWorker(serial, "/request", {
            "serial": serial,
            "event": "evaluate"
        }, files=files)

        # files closed by requests

        return res
