# Run: python scripts/build_package.py (Windows after frontend build)
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH)
frontend = Path(os.environ.get('ORION_FRONTEND_DIST', root / 'frontend' / 'dist'))
if not (frontend / 'index.html').is_file():
    raise RuntimeError('Build the production frontend before packaging.')
datas = [(str(frontend), 'frontend')]
for package in ('guessit', 'rebulk', 'babelfish'):
    datas += collect_data_files(package)
for distribution in ('guessit', 'rebulk', 'babelfish', 'keyring'):
    datas += copy_metadata(distribution)
a = Analysis(
    [str(root / 'scripts' / 'package_entry.py')],
    pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=collect_submodules('keyring.backends') + [
        'uvicorn.logging', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.h11_impl',
        'uvicorn.lifespan.on', 'PIL.Image', 'PIL.JpegImagePlugin', 'PIL.PngImagePlugin', 'PIL.WebPImagePlugin',
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'tkinter', 'pytest'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Orion', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Orion')
