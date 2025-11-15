import re
import subprocess
from pexpect import fdpexpect
import os

def get_env_default(var, default, logger):
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")
    
    return value

def check_default(devpath):
    # TODO 
    # Sometimes closing the fd takes a long time (> 10s) on some firmwares,
    # this might create issues. I'm not really sure what the cause is, I added 
    # a read from stdio to the default firmware and it seems to fix the issue.
    # The same behavior happens from opening and closing the file in C.
    try:
        with open(devpath, "r") as f:
            p = fdpexpect.fdspawn(f, timeout=2)
            p.expect("default firmware", timeout=2)

    except Exception:
        return False
    
    return True

def get_ip():
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    return re.search("[0-9]{3}\\.[0-9]{3}\\.[0-9]\\.[0-9]{3}", str(res)).group(0)


