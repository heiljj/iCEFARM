from icefarm.worker.device.state.core import AbstractState

class ReadyState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        try:
            self.database.updateDeviceStatus(self.serial, "available")
        except Exception:
            self.logger.error("failed to update device status in database to available")
