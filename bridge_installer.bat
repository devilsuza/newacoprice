@echo off
cd /d "%~dp0"
python -m pip install -r print_bridge_requirements.txt
start "Fresmart Bridge" /min python fresmart_render_print_bridge.py
pause
