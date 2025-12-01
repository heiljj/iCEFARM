"""
Utility functions that don't fit the other modules.
"""
from logging import Logger
import re
import subprocess
import os
import inspect
import types

from pexpect import fdpexpect

def get_env_default(var, default: str, logger: Logger):
    """Obtains an environment variable. If its not configured, it instead returns 
    the default value and logs a warning message."""
    value = os.environ.get(var)

    if not value:
        value = default
        logger.warning(f"{var} not configured, defaulting to {default}")

    return value

def check_default(devpath) -> bool:
    """Checks for whether a device is running the default firmware."""
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

def get_ip() -> str:
    """Obtains local network ip from hostname -I."""
    res = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
    group = re.search("[0-9]{3}\\.[0-9]{3}\\.[0-9]\\.[0-9]{3}", str(res))
    if group:
        return group.group(0)

def typecheck(fn, args) -> bool:
    """Checks whether args are valid types for fn. Only works on classes
    and non nested list generics."""
    params = inspect.signature(fn).parameters.values()

    if len(params) != len(args):
        return False

    for arg, param in zip(args, params):
        annotation = param.annotation

        if annotation is inspect._empty:
            continue

        if inspect.isclass(annotation):
            if not isinstance(arg, annotation):
                return False

            continue

        if not isinstance(annotation, types.GenericAlias):
            return False

        if annotation.__origin__ != list or not isinstance(arg, list):
            return False

        if len(annotation.__args__) != 1:
            return False

        type_ = annotation.__args__[0]

        for value in arg:
            if not isinstance(value, type_):
                return False

    return True
