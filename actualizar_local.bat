@echo off
REM ------------------------------------------------------------------
REM  Plan B: actualizar el Estatuto desde este PC (si GitHub no logra
REM  conectarse al normograma DIAN). Programarlo con el Programador de
REM  tareas de Windows, por ejemplo a diario a las 6:30 a. m.
REM  Requiere: Python, Git y el repositorio clonado en esta carpeta.
REM ------------------------------------------------------------------
cd /d "%~dp0"
git pull --rebase
python -m pip install -q -r requirements.txt
python scripts\actualizar.py
if errorlevel 1 goto :fin
git add data
git diff --cached --quiet && goto :fin
git commit -m "Estatuto Tributario: sincronizacion local con normograma DIAN"
git push
REM Al subir, GitHub Actions reconstruye y publica el sitio.
:fin
