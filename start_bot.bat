@echo off
title UPRICH BOT
cd /d D:\uprich-bot-python
echo ============================================
echo   UPRICH BOT  -  http://127.0.0.1:8000
echo   Keep this window OPEN (closing it stops the bot)
echo ============================================
echo.
python -m app.main
echo.
echo [Bot stopped] If there is a red error above, please screenshot it.
pause
