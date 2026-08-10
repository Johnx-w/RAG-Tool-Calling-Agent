"""One-off: generate text-layer PDF from alphacore7_overview.md for Phase 0."""
from pathlib import Path

import fitz

src = Path("data/sample/alphacore7_overview.md")
out = Path("data/sample/alphacore7_overview.pdf")
text = src.read_text(encoding="utf-8")

doc = fitz.open()
page = doc.new_page()
rect = fitz.Rect(50, 50, 545, 792)
# helv 对中文支持差；用内置中文字体回退：逐行插入 cid 字体
font = fitz.Font("cjk")
tw = fitz.TextWriter(page.rect)
tw.fill_textbox(rect, text, font=font, fontsize=11)
tw.write_text(page)
doc.save(out)
doc.close()
print(f"wrote {out} ({out.stat().st_size} bytes)")
