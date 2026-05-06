# -*- mode: python ; coding: utf-8 -*-
import os

# Dynamically find akshare path
try:
    import akshare
    akshare_path = os.path.dirname(akshare.__file__)
except ImportError:
    # Fallback if strictly running without akshare installed in sys.path
    akshare_path = os.path.join('.venv', 'Lib', 'site-packages', 'akshare')

block_cipher = None

a = Analysis(
    ['webview_app/main_pywebview.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('frontend', 'frontend'),
        (akshare_path, 'akshare'),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    a.binaries,
    a.zipfiles,
    a.datas,
    name='KlineTrainerApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='frontend\\assets\\favicon.ico'
)
