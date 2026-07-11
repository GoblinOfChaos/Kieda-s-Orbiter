@echo off
:: Launch Kieda's Orbiter - double-click this if the Start Menu shortcut
:: hasn't been created yet, or if you prefer launching from the folder.
::
:: Uses the .venv's pythonw.exe specifically (not bare "python"): the venv
:: is where PySide6/psutil actually got installed, and pythonw has no
:: console attached so this doesn't pop a terminal window that would kill
:: the app if closed.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launcher.py" app
