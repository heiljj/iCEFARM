import psycopg
import logging
import sys
import os
import requests
from threading import Thread
import schedule
import time
from utils.utils import get_env_default
from control.HeartbeatDatabase import HeartbeatDatabase 

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))

    DATABASE_URL = os.environ.get("USBIPICE_DATABASE")
    if not DATABASE_URL:
        logger.critical("USBIPICE_DATABASE not configured")
        raise Exception("USBIPICE_DATABASE not configured")
    
    HEARTBEAT_POLL = int(get_env_default("USBIPICE_HEARTBEAT_SECONDS", "15", logger))

    TIMEOUT_POLL = int(get_env_default("USBIPICE_TIMEOUT_POLL_SECONDS", "15", logger))
    TIMEOUT_DURATION = int(get_env_default("USBIPICE_TIMEOUT_DURATION_SECONDS", "60", logger))

    RESERVATION_POLL = int(get_env_default("USBIPICE_RESERVATION_POLL", "30", logger))

    RESERVATION_EXPIRING_POLL = int(get_env_default("USBIP_RESERVATION_EXPIRING_POLL_SECONDS"))
    RESERVATION_EXPIRING_NOTIFY_AT = int(get_env_default("USBIP_RESERVATION_EXPIRING_NOTIFY_AT_MINUTES"))

    database = HeartbeatDatabase(DATABASE_URL, logger)


    def heartbeat_workers():
        workers = database.getWorkers()

        if not workers:
            return
        
        for name, ip, port in workers:
            url = f"http://{ip}:{port}/heartbeat"
            try:
                req = requests.get(url)

                if req.status_code != 200:
                    raise Exception
            except:
                logger.error(f"{name} failed heartbeat check")
            else:
                database.heartbeatWorker(name)
            
    
    def send_event(url, serial, event):
        if not url:
            logger.warning(f"device {serial} had event {event} but no callback subscription")
        
        try:
            requests.get(url, data={
                "event": event,
                "serial": serial
            })
        except:
            logger.warning(f"failed to notify {url} device {serial} of {event}")

    def worker_timeouts():
        data = database.getWorkerTimeouts(TIMEOUT_DURATION)
        if data:
            list(map(lambda x : send_event(x[1], x[2], "failure"), data))

    def reservation_notification(serial, url, workerip, workerport):
        send_event(url, serial, "reservation end")
        
        try:
            requests.get(f"http://{workerip}:{workerport}/unreserve", data={
                "serial": serial
            })
        except:
            logger.warning(f"failed to notify worker {workerip}:{workerport} of device {serial} reservation ending")

    def reservation_timeouts():
        data = database.getReservationTimeouts()
        if data:
            list(map(lambda x : reservation_notification(x[0], x[1], x[2], x[3]), data))

    def reservation_ending_soon():
        try:
            with psycopg.connect(DATABASE_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM handleReservationTimeouts(%s::int)", (RESERVATION_EXPIRING_NOTIFY_AT,))

                    data = cur.fetchall()
            
            list(map(lambda x : send_event(x[0], x[1], "reservation ending soon"), data))

        except:
            logger.error("failed to check for reservation timeouts")
            return

    schedule.every(HEARTBEAT_POLL).seconds.do(lambda : Thread(target=heartbeat_workers).start())
    schedule.every(TIMEOUT_POLL).seconds.do(lambda : Thread(target=worker_timeouts).start())
    schedule.every(RESERVATION_POLL).seconds.do(lambda : Thread(target=reservation_timeouts).start())
    schedule.every(RESERVATION_EXPIRING_POLL).minutes.do(lambda : Thread(target=reservation_ending_soon).start())

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()







