from icefarm.worker.device.state.core import AbstractState

class BrokenState(AbstractState):
    def __init__(self, state):
        super().__init__(state)
        try:
            self.database.updateDeviceStatus(self.serial, "broken")
        except Exception:
            self.logger.critical("failed to update device status in database to broken")

        self.logger.error("device is broken")
        self.device_event_sender.sendDeviceFailure()
