cd /d C:\Users\mtrem\TRADING
if not exist "data\health" mkdir "data\health"
.venv\Scripts\python.exe -m monitors.health --db data\quantbot.db >> data\health\health.log 2>&1
