"""Camtek AOI Manager v13 — start file (run by python.org pythonw.exe, no console window).

Two layouts are supported:
  installed  : <home>/python/pythonw.exe · <home>/Camtek_AOI_manager.pyw · <home>/app/ (program)
               An update is prepared as <home>/app.new/ by the running program; it is put in
               place here, before any program module is loaded (a running program cannot
               replace its own files). The old copy is kept as <home>/app.old/ until the next start.
  source copy: this file sits next to param_manager/ (git clone, development).
This file only renames folders inside <home>; it never downloads or runs anything else.
"""
import os
import shutil
import sys

sys.dont_write_bytecode = True        # no __pycache__ next to the program (no extra file churn)
HOME = os.path.dirname(os.path.abspath(__file__))


def _swap(home):
    app, new, old = (os.path.join(home, n) for n in ("app", "app.new", "app.old"))
    ready = os.path.join(new, "param_manager", "launcher.py")
    if not os.path.isdir(app) and os.path.isdir(old):
        os.rename(old, app)                              # a swap was cut off: restore first
    if os.path.isdir(old) and os.path.isdir(app):
        shutil.rmtree(old, ignore_errors=True)          # the previous update worked
    if not os.path.isfile(ready):
        return
    try:
        if os.path.isdir(app):
            os.rename(app, old)
        os.rename(new, app)
    except OSError:
        if not os.path.isdir(app) and os.path.isdir(old):
            os.rename(old, app)                          # put the working copy back


def _app_dir():
    if os.path.isdir(os.path.join(HOME, "param_manager")):
        return HOME, None                                # source copy
    _swap(HOME)
    return os.path.join(HOME, "app"), HOME


APP, INSTALLED = _app_dir()
if INSTALLED:
    os.environ["PARA_APP_HOME"] = INSTALLED
sys.path[:0] = [APP, os.path.join(APP, "vendor")]

if __name__ == "__main__":
    from param_manager import launcher
    raise SystemExit(launcher.main())
