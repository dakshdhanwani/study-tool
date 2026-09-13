@echo off
echo Starting Course Companion...
cd /d "%~dp0"
streamlit run src/app/main.py
pause
