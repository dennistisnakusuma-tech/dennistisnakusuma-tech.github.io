"""Portfolio phone check: iPhone (WebKit) + Android (Edge mobile emulation).
Scenarios: normal finger scroll, IntersectionObserver removed (fallback path),
fast fling. Asserts every stat ends visible with its final text."""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = Path(__file__).with_name("out_stats")
OUT.mkdir(exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()

PROBE = """() => [...document.querySelectorAll('.stat')].map(el => ({
  in: el.classList.contains('in'), op: +getComputedStyle(el).opacity,
  wc: getComputedStyle(el).willChange, text: el.querySelector('.num').textContent.trim() }))"""
EXPECT = ["7+", "Trillions", "Millions"]
fails = []


def scenario(engine, browser, device, name, kill_io=False, fling=False):
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if kill_io:
        page.add_init_script("delete window.IntersectionObserver;")
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(1200)
    top = page.evaluate("() => document.querySelector('#stats').getBoundingClientRect().top + scrollY")
    h = page.evaluate("() => document.querySelector('#stats').offsetHeight")
    vh = page.evaluate("() => innerHeight")
    if fling:
        page.evaluate(f"window.scrollTo(0, {int(top + h - vh * .5)})")   # jump straight past most of it
        page.wait_for_timeout(250)
    else:
        y = int(max(0, top - vh))
        while y <= top + h:
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(250)
            y += 150
    page.wait_for_timeout(1800)   # let fades + count-up finish
    # look at each stat in turn so the screenshot shows it
    for i in range(3):
        page.evaluate(f"document.querySelectorAll('.stat')[{i}].scrollIntoView({{block:'center'}})")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / f"{engine}_{name}_{i}.png"))
    st = page.evaluate(PROBE)
    ok = all(s["in"] and s["op"] > 0.99 and s["text"] == e for s, e in zip(st, EXPECT)) and not errors
    print(f"[{'PASS' if ok else 'FAIL'}] {engine:7s} {name:10s} " +
          "  ".join(f"{s['text']}(op{s['op']:.2f},wc={s['wc']})" for s in st) + (f"  errors={errors}" if errors else ""))
    if not ok:
        fails.append(f"{engine}/{name}")
    ctx.close()


with sync_playwright() as p:
    for engine, launch, device in (("iphone", lambda: p.webkit.launch(), p.devices["iPhone 14"]),
                                   ("android", lambda: p.chromium.launch(channel="msedge"), p.devices["Pixel 7"])):
        b = launch()
        scenario(engine, b, device, "normal")
        scenario(engine, b, device, "no-IO", kill_io=True)
        scenario(engine, b, device, "fling", fling=True)
        b.close()
print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
