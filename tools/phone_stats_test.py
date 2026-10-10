"""Phone check of the pinned stats scene (7+ -> Trillions -> Millions swapping
in place, like desktop) on iPhone (WebKit) and Android (Edge mobile emulation).

Checks: the scene pins (sticky works), the right number owns each third,
"empty" screens are rare, 7+ counts up, a fast fling lands on the right
number, and no JS errors. Saves frames to out_stats/.

    python tools/phone_stats_test.py file:///.../index.html
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = Path(__file__).with_name("out_stats")
OUT.mkdir(exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()

STATE = """() => {
  const st = document.querySelector('#stats'), sticky = document.querySelector('.stats-sticky');
  const r = st.getBoundingClientRect();
  return { progress: Math.min(1, Math.max(0, -r.top / (r.height - innerHeight))),
           stickyTop: Math.round(sticky.getBoundingClientRect().top), sectionTop: Math.round(r.top),
           ops: [...document.querySelectorAll('.stat')].map(s => +getComputedStyle(s).opacity),
           first: document.querySelector('.stat .num').textContent.trim() };
}"""
NAMES = ["7+", "Trillions", "Millions"]
fails = []


def check(engine, ok, msg):
    print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
    if not ok:
        fails.append(f"{engine}: {msg}")


def run(engine, browser, device):
    print(f"== {engine}")
    ctx = browser.new_context(**device)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load", timeout=60000)
    page.wait_for_timeout(1200)
    top = page.evaluate("document.querySelector('#stats').getBoundingClientRect().top + scrollY")
    h = page.evaluate("document.querySelector('#stats').offsetHeight")
    vh = page.evaluate("innerHeight")
    print(f"  section height = {h/vh:.2f} screens")

    # finger-like scroll through the whole scene, sampling every step
    samples, y = [], int(top - vh * .6)
    while y <= top + h - vh + 40:
        page.evaluate(f"window.scrollTo(0,{y})")
        page.wait_for_timeout(120)
        samples.append(page.evaluate(STATE))
        y += int(vh * .06)
    pinned = [s for s in samples if s["sectionTop"] <= 0 and s["progress"] < 1]
    check(engine, all(abs(s["stickyTop"]) <= 1 for s in pinned), f"scene stays pinned while scrolling ({len(pinned)} samples)")
    entering = [s for s in samples if 0 < s["sectionTop"] < vh * .6]
    check(engine, all(s["ops"][0] > .99 for s in entering), "7+ already visible while the scene scrolls in (no empty screen)")
    for name, lo, hi, idx in (("7+", .05, .25, 0), ("Trillions", .42, .58, 1), ("Millions", .75, 1.0, 2)):
        win = [s for s in pinned if lo <= s["progress"] <= hi]
        good = win and all(s["ops"][idx] > .99 and sum(o > .05 for o in s["ops"]) == 1 for s in win)
        check(engine, bool(good), f"only '{name}' shown around progress {lo:.2f}-{hi:.2f}")
    dark = [s for s in pinned if max(s["ops"]) < .3]
    check(engine, len(dark) / max(1, len(pinned)) < .12, f"near-empty screens: {len(dark)}/{len(pinned)} samples")
    check(engine, samples[-1]["first"] == "7+", f"7+ finished counting (shows '{samples[-1]['first']}')")

    # frames at the three resting points + one mid-swap
    for tag, frac in (("1_7plus", .15), ("2_swap", .33), ("3_trillions", .5), ("4_millions", .85)):
        page.evaluate(f"window.scrollTo(0,{int(top + (h - vh) * frac)})")
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / f"{engine}_{tag}.png"))

    # fast fling from the top of the page straight into the middle of the scene
    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(300)
    page.evaluate(f"window.scrollTo(0,{int(top + (h - vh) * .5)})")
    page.wait_for_timeout(500)
    s = page.evaluate(STATE)
    check(engine, s["ops"][1] > .99 and s["ops"][0] < .05 and s["ops"][2] < .05, "fling lands on 'Trillions' only")
    check(engine, not errors, f"no JS errors {errors or ''}")
    ctx.close()


with sync_playwright() as p:
    b = p.webkit.launch()
    run("iphone", b, p.devices["iPhone 14"])
    b.close()
    b = p.chromium.launch(channel="msedge")
    run("android", b, p.devices["Pixel 7"])
    b.close()
print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
