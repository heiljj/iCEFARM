from __future__ import annotations
from logging import Logger, LoggerAdapter
import threading
import time

import requests
import schedule

from icefarm.control import ControlDatabase
from icefarm.utils.Database import DatabaseException

import typing
if typing.TYPE_CHECKING:
    from icefarm.control import ControlEventSender

# TODO get values from config
class HeartbeatConfig:
    def __init__(self):
        self.heartbeat_poll_seconds: str = 15
        self.timeout_poll_seconds: str = 15
        self.timeout_duration_seconds: str = 180
        self.reservation_poll_seconds: str = 30
        self.reservation_expiring_poll_seconds: str = 300
        self.reservation_expiring_notify_at_seconds: str = 20 * 60
        self.heartbeat_request_timeout_seconds: str = 30

class HeartbeatLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[Heartbeat] {msg}", kwargs

class Heartbeat:
    def __init__(self, event_sender: ControlEventSender, database_url: str, config: HeartbeatConfig, logger: Logger):
        self.event_sender = event_sender
        self.logger = HeartbeatLogger(logger)
        self.database = ControlDatabase(database_url, logger)
        self.config = config
        self.thread = None

    def start(self):
        self.__startHeartBeatWorkers()
        self.__startWorkerTimeouts()
        self.__startReservationTimeouts()
        self.__startReservationEndingSoon()

        def run():
            while True:
                schedule.run_pending()
                time.sleep(1)

        self.thread = threading.Thread(target=run, daemon=True, name="heartbeat")
        self.thread.start()

    def __startHeartBeatWorkers(self):
        def do():
            def run():
                try:
                    workers = self.database.getWorkers()
                except DatabaseException:
                    self.logger.critical("Failed to fetch workers for heartbeat")
                    return

                if not workers:
                    return

                for row in workers:
                    name = row.id
                    wurl = row.wurl

                    url = f"{wurl}/heartbeat"
                    try:
                        req = requests.get(url, timeout=self.config.heartbeat_request_timeout_seconds)

                        if req.status_code != 200:
                            raise Exception
                    except Exception:
                        self.logger.error(f"{name} failed heartbeat check")
                        continue

                    self.logger.debug(f"heartbeat success for {name}")

                    try:
                        self.database.heartbeatWorker(name)
                    except DatabaseException:
                        self.logger.error(f"failed to update heartbeat for {name}")

            threading.Thread(target=run, name="heartbeat-worker", daemon=True).start()

        schedule.every(self.config.heartbeat_poll_seconds).seconds.do(do)

    def __startWorkerTimeouts(self):
        def do():
            def run(timeout_dur=self.config.timeout_duration_seconds):
                try:
                    data = self.database.getWorkerTimeouts(timeout_dur)
                except DatabaseException:
                    self.logger.critical("failed to fetch worker timeouts")
                    return

                for row in data:
                    self.event_sender.sendDeviceFailure(row.serial_id, row.client_id)
                    self.logger.info(f"Worker {row.worker_id} failed; sent device failure for client {row.client_id} device {row.serial_id}")

            threading.Thread(target=run, name="heartbeat-worker-timeouts", daemon=True).start()

        schedule.every(self.config.timeout_poll_seconds).seconds.do(do)

    def __startReservationTimeouts(self):
        def do():
            def run():
                try:
                    data = self.database.getReservationTimeouts()
                except DatabaseException:
                    self.logger.critical("failed to fetch reservation timeouts")
                    return

                for row in data:
                    self.logger.info(f"Reservation for device {row.device_id} by client {row.client_id} ended")

            threading.Thread(target=run, name="heartbeat-reservation-timeouts", daemon=True).start()

        schedule.every(self.config.reservation_poll_seconds).seconds.do(do)

    def __startReservationEndingSoon(self):
        def do():
            def run(notify_at=self.config.reservation_expiring_notify_at_seconds):
                try:
                    data = self.database.getReservationEndingSoon(notify_at)
                except DatabaseException:
                    self.logger.critical("failed to fetch reservations ending soon")
                    return

                for serial in data:
                    self.event_sender.sendDeviceReservationEndingSoon(serial)

            threading.Thread(target=run, name="heartbeat-reservation-ending-soon", daemon=True).start()

        schedule.every(self.config.reservation_expiring_poll_seconds).seconds.do(do)
