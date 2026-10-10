# Phone checks (run before every push)

Real phone engines via Playwright: WebKit = iPhone Safari (and every iOS browser),
Chromium mobile emulation = Android. Needs `pip install playwright pillow` and
`python -m playwright install webkit` (Android uses the installed Edge).

    python tools/phone_stats_test.py file:///.../index.html   # stats: normal / no-IntersectionObserver / fling
    python tools/phone_full_test.py  file:///.../index.html   # every screen, overflow, JS errors, gallery

Both must print `RESULT: ALL PASS`. Re-run against the live URL after GitHub Pages updates.
