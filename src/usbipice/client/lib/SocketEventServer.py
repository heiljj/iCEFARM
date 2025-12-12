from __future__ import annotations
from logging import Logger, LoggerAdapter
import threading
import json

import socketio

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from usbipice.client.lib import AbstractEventHandler

class EventLogger(LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[EventServer] {msg}", kwargs

class SocketLogger(LoggerAdapter):
    def __init__(self, logger, url, extra = None):
        super().__init__(logger, extra)
        self.url = url

    def process(self, msg, kwargs):
        return f"[socket@{self.url}] {msg}", kwargs

class Event:
    def __init__(self, serial, event, contents):
        self.serial = serial
        self.event = event
        self.contents = contents

class SocketEventServer:
    """Hosts a server for the workers and heartbeat process to send events to. When an event is received,
    it calls the corresponding method of the EventHandlers starting at the 0 index."""
    def __init__(self, logger: Logger, eventhandlers: list[AbstractEventHandler]):
        self.logger = EventLogger(logger)
        self.eventhandlers = eventhandlers

        self.socket_lock = threading.Lock()
        self.sockets = {}
        self.dont_reconnect = set()

    def handleEvent(self, event: Event):
        for eh in self.eventhandlers:
            eh.handleEvent(event)

    def connectWorker(self, url):
        with self.socket_lock:
            if url in self.sockets:
                return True

            sio = socketio.Client()
            self.sockets[url] = sio

            logger = SocketLogger(self.logger, url)

            @sio.event
            def connect():
                logger.info("connected")
            @sio.event
            def connect_error(_):
                logger.error("connection attempt failed")
            @sio.event
            def disconnect(reason):
                logger.error(f"disconnected: {reason}")
            @sio.on("event")
            def handle(data):
                try:
                    msg = json.loads(data)
                except Exception:
                    logger.error("received unparsable data")
                    return

                serial = msg.get("serial")
                event = msg.get("event")
                contents = msg.get("contents")

                if not serial or not event or not contents:
                    logger.error("bad event contents")
                    return

                logger.debug(f"received {event} event")
                event = Event(serial, event, contents)
                self.handleEvent(event)

            sio.connect(url)

    def sendWorker(self, url, event, data):
        with self.socket_lock:
            sio = self.sockets.get(url)

            if not sio:
                return False

            sio.emit(event, data)

            return True

    def disconnectWorker(self, url):
        with self.socket_lock:
            sio = self.sockets.get(url)

            if not sio:
                return True

            sio.disconnect()

            del self.sockets[url]

    def exit(self):
        for eh in self.eventhandlers:
            eh.exit()

        for url in self.sockets:
            self.disconnectWorker(url)
