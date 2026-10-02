$ErrorActionPreference = "Stop"

python -m pip install --upgrade pip
python -m pip install pyinstaller customtkinter pillow certifi

python -c "from PIL import Image; img=Image.open('aca_platform_icon.png').convert('RGBA'); img.save('aca_platform_icon.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name "ACA Platform" `
  --icon "aca_platform_icon.ico" `
  --collect-all customtkinter `
  --collect-data certifi `
  --add-data "aca_platform_icon.png;." `
  aca_platform.py

Write-Host ""
Write-Host "DONE:"
Write-Host (Resolve-Path "dist\\ACA Platform.exe")
