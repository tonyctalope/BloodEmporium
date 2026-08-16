"""Produces references/inspo1.ico, which onedir.spec uses as the executable's icon.

references/ is gitignored upstream, so the icon is regenerated from the PNG the app already ships.
"""
import os

from PIL import Image

os.makedirs("references", exist_ok=True)
Image.open("assets/images/inspo1.png").save(
    "references/inspo1.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("references/inspo1.ico written")
