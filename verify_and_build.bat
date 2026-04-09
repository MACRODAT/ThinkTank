@echo off
cd /d D:\ai\central-think-tank

echo === Verifying agent_runner.py ===
python -m py_compile core\agent_runner.py && echo agent_runner OK || echo agent_runner FAIL

echo === Patching agents.py ===
python patch_agents_chat.py

echo === Verifying settings.py ===
python -m py_compile api\routes\settings.py && echo settings OK || echo settings FAIL

echo === Installing httpx if needed ===
pip install httpx --break-system-packages -q

echo === Copying new Settings.jsx ===
copy "%~dp0Settings.jsx" "frontend\src\pages\Settings\Settings.jsx"

echo === Building frontend ===
cd frontend
npm run build
cd ..

echo === Done. Restart the server: python run.py ===
pause
