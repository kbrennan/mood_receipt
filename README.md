# Mood Receipt

Pick a mood on a touch screen and get a generative art receipt, seeded by the current second, printed on a thermal label printer. Built for a Raspberry Pi 5 with a 720x1280 portrait touch display and a Polono PL80E with 4x6 labels.

## Run it

- **Kiosk:** press `Ctrl+Alt+K`, open "Mood Receipt Kiosk" from the app menu, or run `kiosk/mood-kiosk.sh`.
- **Leave the kiosk:** hold the MOOD-O-MATIC name at the top of the screen for 3 seconds, press `Ctrl+Alt+K`, or run `kiosk/mood-kiosk.sh stop`.
- **Without the kiosk or real printing:** run `python3 server.py --dry-run /tmp` and open http://127.0.0.1:8765/. Print jobs are saved to `last.tspl` in that folder.

`?mood=<0-15>&t=<epoch seconds>` on the URL recreates one exact receipt. Run the tests with `python3 tests/test_tspl.py`.

## How it fits together

- `static/index.html` draws the receipt with p5.js at 800x1200 dots, which is a 4x6 label at 203 dpi. p5 and the fonts are in `static/vendor`, so no internet is needed.
- `server.py` is a Flask server on 127.0.0.1:8765. It turns the PNG into a TSPL job and sends it to the CUPS raw queue `PL80E`.
- `kiosk/mood-kiosk.sh` starts the server and Chromium with its own profile, and stops both together.

## Setup outside this repo

Needs a CUPS raw queue named `PL80E`, plus `python3-flask` and `python3-pil`.

`~/.config/labwc/rc.xml` puts the kiosk on the touch screen and adds the shortcut. Apply changes with `labwc --reconfigure`:

```xml
<keyboard>
  <keybind key="C-A-k">
    <action name="Execute" command="/home/kbrennan/mood_receipt/kiosk/mood-kiosk.sh toggle"/>
  </keybind>
</keyboard>
<windowRules>
  <windowRule identifier="mood-receipt" serverDecoration="no">
    <action name="MoveToOutput" output="DSI-2"/>
  </windowRule>
</windowRules>
```

The app menu entry is `~/.local/share/applications/mood-receipt.desktop`, which runs `kiosk/mood-kiosk.sh start`.
