# Speech Volume Boost (NVDA add-on)

Amplifies NVDA speech volume for **any** synthesizer. The add-on applies a gain to
NVDA's speech audio stream *after* the synthesizer renders it, so it works with
eSpeak NG, OneCore, SAPI5, SAPI4 and third-party synthesizer drivers alike,
without touching the synthesizer's own (0–100) volume setting.

It works by hooking `nvwave.WavePlayer.feed` in the main NVDA process — every
synthesizer funnels its 16-bit speech PCM through this single method — and
scaling the samples by a user-configurable gain (100% unchanged, up to 400%).

Requires **NVDA 2026.1 or later (64-bit)**. Pure Python, no bundled binaries.

## Layout

```
speechVolumeBoost/
├── src/                  # central add-on source folder (zipped into the package)
│   ├── manifest.ini
│   ├── globalPlugins/
│   │   └── speechVolumeBoost.py
│   └── doc/en/readme.html
├── build.py              # packages src/ into a .nvda-addon in dist/
├── dist/                 # built .nvda-addon files
└── README.md
```

## Building

```
python build.py
```

Produces `dist/speechVolumeBoost-0.1.0.nvda-addon`.

## Installing / testing

1. Install the `.nvda-addon` via NVDA's Tools → Add-on Store → Install from file
   (or run NVDA and open the package file).
2. Restart NVDA.
3. Press `NVDA+alt+g` to toggle the boost, or open NVDA Settings → Speech Volume
   Boost to configure it.

For quick development iteration you can skip packaging: enable the developer
scratchpad (NVDA Settings → Advanced → Developer Scratchpad) and copy
`src/globalPlugins/speechVolumeBoost.py` to the scratchpad's `globalPlugins`
folder, then use NVDA's Tools → Reload Plugins.

## Commands

| Gesture | Action |
| --- | --- |
| `NVDA+alt+g` | Toggle the boost |
| `NVDA+alt+shift+g` | Increase gain by 10% |
| `NVDA+alt+control+g` | Decrease gain by 10% |
| `NVDA+alt+control+shift+g` | Report state and gain |

All gestures are remappable in NVDA's Input Gestures dialog under
"Speech Volume Boost".

## How it works

- `WavePlayer.feed` is monkey-patched once at add-on load.
- Only players with purpose `AudioPurpose.SPEECH` and 16-bit PCM are processed;
  sounds, tones and other formats pass through untouched.
- Each chunk is converted to a 16-bit sample array, multiplied by the gain, and
  clamped to the int16 range to avoid wraparound.
- The processed bytes are handed to the original `feed` with identical size and
  the same `onDone` callback, preserving NVDA's audio bookkeeping.

## Notes / limitations

- At high gains the signal may reach the 16-bit maximum and clip. Lower the gain
  if you hear distortion.
- The gain applies to speech spoken *after* a change; audio already buffered is
  unaffected.

## License

GPL-2.0-or-later (same as NVDA).
