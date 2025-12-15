import os
import logging
import sys

import requests
from flask import Flask, request, Response, jsonify
from waitress import serve

from usbipice.control import ServerDatabase, Control
from usbipice.utils import DeviceEventSender

def argify_json(parms: list[str], types: list[type]):
    """Obtains the json values of keys in the list from the flask Request and unpacks them into fun, starting with the 0 index."""
    if request.content_type != "application/json":
        return False
    try:
        json = request.get_json()
    except Exception:
        return False

    args = []

    for p, t in zip(parms, types):
        value = json.get(p)
        if value is None or not isinstance(value, t):
            return False
        args.append(value)

    if len(args) != len(parms):
        return False

    return args

def expect(fn, arg):
    if not arg or (out := fn(*arg)) is False:
        return Response(status=400)

    return jsonify(out)

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        raise Exception("USBIPICE_DATABASE not configured")

    SERVER_PORT = int(os.environ.get("USBIPICE_CONTROL_PORT", "8080"))
    logger.info(f"Running on port {SERVER_PORT}")


    # TODO handle socket routing
    event_sender = DeviceEventSender(DATABASE_URL, logger)
    control = Control(DATABASE_URL, event_sender, logger)
    app = Flask(__name__)

    @app.get("/reserve")
    def make_reservations():
        return expect(control.reserve, argify_json(["amount", "name", "kind", "args"], [int, str, str, dict]))

    @app.get("/extend")
    def extend():
        return expect(control.extend, argify_json(["name", "serials"], [str, list]))

    @app.get("/extendall")
    def extendall():
        return expect(control.extendAll, argify_json(["name"], [str]))

    @app.get("/end")
    def end():
        return expect(control.end, argify_json(["name", "serials"], [str, list]))

    @app.get("/endall")
    def endall():
        return expect(control.end, argify_json(["name"], [str]))

    @app.get("/log")
    def log():
        if not (args := argify_json(["logs", "name"], [list, str])):
            return Response(status=400)

        control.log(*args, request.remote_addr[0])
        return Response(status=200)

    serve(app, port=SERVER_PORT)


if __name__ == "__main__":
    main()
