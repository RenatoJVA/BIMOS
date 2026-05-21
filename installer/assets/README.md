# BIMOS Installer — Asset Checklist

Place the following files in this directory **before** running `builder.py`.
They are not committed to git because they are binary assets.

| File | Platform | Required | Description |
|---|---|---|---|
| `bimos.ico` | Windows | **Yes** | 256×256 `.ico` for NSIS wizard and exe |
| `bimos.icns` | macOS | **Yes** | `.icns` bundle icon for the .app |
| `bimos.png` | Linux | **Yes** | 256×256 PNG for .deb package |
| `wizard_banner.bmp` | Windows | Optional | 164×314 px sidebar BMP for NSIS wizard |
| `header.bmp` | Windows | Optional | 150×57 px header BMP for NSIS pages |
| `dmg_background.png` | macOS | Optional | 660×400 px background image for the DMG window |
| `LICENSE.rtf` | Windows | **Yes** | RTF license shown in NSIS wizard (already created) |

## Generating from a PNG source

If you only have a single `bimos.png` (512×512 recommended), run:

```bash
# macOS .icns
mkdir -p bimos.iconset
sips -z 16 16     bimos.png --out bimos.iconset/icon_16x16.png
sips -z 32 32     bimos.png --out bimos.iconset/icon_16x16@2x.png
sips -z 32 32     bimos.png --out bimos.iconset/icon_32x32.png
sips -z 64 64     bimos.png --out bimos.iconset/icon_32x32@2x.png
sips -z 128 128   bimos.png --out bimos.iconset/icon_128x128.png
sips -z 256 256   bimos.png --out bimos.iconset/icon_128x128@2x.png
sips -z 256 256   bimos.png --out bimos.iconset/icon_256x256.png
sips -z 512 512   bimos.png --out bimos.iconset/icon_256x256@2x.png
iconutil -c icns bimos.iconset

# Windows .ico  (requires ImageMagick)
convert bimos.png -define icon:auto-resize=256,128,64,48,32,16 bimos.ico
```
