"""Whole-page phone regression: every screen top->bottom, horizontal overflow,
JS errors, invisible-but-should-be-visible elements, gallery swipe."""
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = Path(__file__).with_name("out_full")
OUT.mkdir(exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()

HIDDEN = """() => [...document.querySelectorAll('.rv, .card, .tile, .cc, h1, h2')]
  .filter(el => { const r = el.getBoundingClientRect(); return r.bottom < innerHeight * .8 && r.bottom > 0 && r.height > 0; })
  .filter(el => +getComputedStyle(el).opacity < .5)
  .map(el => (el.className || el.tagName) + ':' + (el.textContent || '').trim().slice(0, 30))"""

problems = []
with sync_playwright() as p:
    for engine, launch, device in (("iphone", lambda: p.webkit.launch(), p.devices["iPhone 14"]),
                                   ("android", lambda: p.chromium.launch(channel="msedge"), p.devices["Pixel 7"])):
        b = launch()
        page = b.new_context(**device).new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(URL, wait_until="load", timeout=60000)
        page.wait_for_timeout(1500)
        vh = page.evaluate("innerHeight")
        total = page.evaluate("document.documentElement.scrollHeight")
        frames, y, hidden_hits = [], 0, set()
        while y < total:
            page.evaluate(f"window.scrollTo(0,{y})")
            page.wait_for_timeout(1300)
            for h in page.evaluate(HIDDEN):
                hidden_hits.add(h)
            f = OUT / f"{engine}_{y:05d}.png"
            page.screenshot(path=str(f))
            frames.append(f)
            y += int(vh * .9)
        overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
        # gallery swipe: every card must be visible after swiping
        page.evaluate("document.getElementById('gallery').scrollIntoView({block:'center'})")
        page.wait_for_timeout(800)
        card_ops = []
        for _ in range(5):
            page.evaluate("document.getElementById('gallery').scrollBy({left: 340})")
            page.wait_for_timeout(500)
        card_ops = page.evaluate("[...document.querySelectorAll('.card')].map(c => +getComputedStyle(c).opacity)")
        print(f"{engine}: screens={len(frames)} overflowX={overflow} cardsOpacity={card_ops} errors={errs or 'none'}")
        print(f"   elements still invisible after scrolling past them: {sorted(hidden_hits) or 'none'}")
        if overflow or errs or hidden_hits or min(card_ops) < .99:
            problems.append(engine)
        # contact sheet
        ims = [Image.open(f).resize((156, 266)) for f in frames]
        sheet = Image.new("RGB", (len(ims) * 160, 266), "#f0f")
        for i, im in enumerate(ims):
            sheet.paste(im, (i * 160, 0))
        sheet.save(OUT / f"{engine}_sheet.png")
        b.close()
print("RESULT:", "ALL PASS" if not problems else f"PROBLEMS: {problems}")
