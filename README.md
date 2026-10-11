# Euan Paint

A fullscreen painting app for toddlers. Big buttons, bright colours, silly
sounds, and no easy way out.

## What it does

| Do this | And this happens |
| --- | --- |
| Scroll the mouse wheel | Changes colour. Plays a note, then says the colour's name out loud. The list wraps round forever. |
| Left (or middle) click and drag | Paints with the current tool |
| Right click | Switches to stamps; right click again for the next stamp |
| Press any key | A random shape pops up somewhere on the page |
| Lost the pointer? Wiggle the mouse | The pointer pops up big for a moment. Near the screen edges it also sends out rainbow ripples so it's easy to spot. |

**Toolbar (left):**

- **Brush**: paints in the current colour.
- **Rainbow star**: a smiling gold star that paints a rainbow behind it,
  leaving twinkles and tinkly sounds. Every few seconds a burst of sparkles
  races along one of the rainbows.
- **Railway**: lays down train track (wooden sleepers and steel rails) wherever
  you draw, with a tunnel at each end. One train with rainbow carriages tours
  all the tracks: it goes into a tunnel and comes out of a tunnel on the next
  track, as if the tunnels were joined underground. A newly drawn track is
  where it goes next. The train drives over the picture but isn't painted into
  it, so it doesn't show up in saved pictures.
- **Glitter**: scatters twinkly sparkles and gold glitter in the current colour.
- **Bucket**: tap inside a shape to fill it with colour. The paint spreads out
  in a ripple from where you tapped.
- **Eraser**: rubs out.
- **Size**: switches between small, medium and big. It changes the brush,
  rainbow star, railway (and its train), eraser and stamps.
- **Undo** (curly blue arrow): takes back the last thing done. Press it again
  to go further back, up to 20 steps. It can even bring back a page that was
  cleared with the bin.
- **Bin**: clears the page. The picture is saved first, so nothing is lost.

**Stamps (right):** star, heart, smiley, flower, sun, fish, car, train,
butterfly and rocket. They come out in the current colour with a pop and
confetti, and each one makes its own noise: the car beeps, the fish blows
bubbles, the rocket whooshes, the train toots. Drag to leave a trail of them.

**Colours (bottom):** 14 swatches. Click one, or just scroll.

## Setup

You need Python 3, `pygame-ce` (or `pygame`) and `numpy`. The app still runs
without numpy, but has no sound and the bucket does nothing.

```bash
pip install pygame-ce numpy
```

Speaking the colour names uses `spd-say`, which comes with Ubuntu. If it's
missing, the app just doesn't speak.

To add Euan Paint to your app menu:

```bash
./install.sh
```

Or run it directly:

```bash
python3 euan_paint.py
```

### Windows

To make a stand-alone `Euan Paint.exe` (no Python needed on the PC that runs it):

1. On a Windows PC, install Python 3 from python.org and tick
   **"Add python.exe to PATH"**. This is only needed for the build.
2. Copy this folder over and double-click **`build_windows.bat`**. It downloads
   what it needs and takes a minute or two.
3. The finished app is `dist\Euan Paint.exe` (about 40 MB). Copy it anywhere,
   then right-click it to pin it to Start or the taskbar.

On Windows, colour names aren't spoken (that uses Linux's `spd-say`).
Everything else works the same, including the exit combo. The Windows key and
Alt+Tab are blocked while it runs, but Ctrl+Alt+Del always works (no app can
block it). The first launch can take a few seconds while the exe unpacks.

## For grown-ups

**To exit: hold Ctrl + Shift + Q, and nothing else, for 3 seconds.** A ring
fills up on screen while you hold. If you let go early, nothing happens.
Forgot the combo? Press **Esc** and a reminder pops up for a few seconds.

**Ctrl + Z** undoes, the same as the undo button.

**Volume keys** on the keyboard work while the app is running, with a little
volume bar at the top of the screen. (The app holds onto the keyboard so Euan
can't escape, which means the desktop never sees those keys, so the app changes
the volume itself. On Linux it uses `wpctl`, `pactl` or `amixer`, whichever is
installed.) Volume and media keys never stamp shapes.

**Toddler-proofing:**

- It runs fullscreen and keeps hold of the mouse and keyboard.
- Closing the window (Alt+F4 and similar) is ignored.
- Ordinary keys only stamp shapes.
- **GNOME:** the first time it runs, GNOME asks whether Euan Paint may
  *inhibit shortcuts*. Choose **Allow**, so the Super key and Alt+Tab stay
  inside the app.
- **Not blocked:** an app can't stop Ctrl+Alt+F1–F12 (switching to a text
  console) or the power button.

**Saved pictures** go to `~/Pictures/Euan Paint/`. The current picture is
saved whenever the page is cleared and when the app exits, but only if
something was drawn.

**Options:**

| Flag | Effect |
| --- | --- |
| `--windowed` | Opens in a normal window you can close, for trying things out |
| `--no-sound` | No sound effects |
| `--no-voice` | Doesn't say colour names |
| `--make-icon FILE.png` | Writes the app icon to a file and exits (used by `install.sh`) |

## Troubleshooting

- **The Super key or Alt+Tab still escapes.** You may have chosen "Deny" at the
  shortcuts prompt. Run the app from a terminal with
  `SDL_VIDEODRIVER=wayland python3 euan_paint.py`. If it still escapes, check
  Settings → Apps → Euan Paint for the shortcuts permission.
- **No sound.** Check that numpy is installed. The reason sound is off is
  printed in the terminal.
- **Stuck and the exit combo doesn't work.** Switch to a console with
  Ctrl+Alt+F3, log in, and run `pkill -f euan_paint.py`. Then go back with
  Ctrl+Alt+F2 (on some setups it's F1).
