@echo off
chcp 65001 >nul
cd /d "D:\Workspace\llm\daily"
python scheduler.py --once --rotate
