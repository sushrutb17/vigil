# VIGIL narration recording pack

Record each scene as a separate mono WAV file. The six scripts in this folder
are the recording source of truth and are written to the visual beats already
rendered by HyperFrames.

| Scene | Picture duration | Words | Script | Recording target | Output filename |
|---|---:|---:|---|---:|---|
| 1 — Friction | 28s | 67 | `scene-01-friction.txt` | 25–27s | `seg1.wav` |
| 2 — Architecture | 30s | 72 | `scene-02-architecture.txt` | 27–29s | `seg2.wav` |
| 3 — Live execution | 85s | 173 | `scene-03-live.txt` | 80–83s | `seg3.wav` |
| 4 — Failure tolerance | 20s | 41 | `scene-04-failure.txt` | 18–19s | `seg4.wav` |
| 5 — Results | 35s | 79 | `scene-05-results.txt` | 32–34s | `seg5.wav` |
| 6 — Close | 34s | 75 | `scene-06-close.txt` | 29–31s | `seg6.wav` |

Recording setup:

- Record at 48 kHz, mono, WAV; 16-bit or 24-bit PCM is fine.
- Leave roughly half a second of room tone before the first word and after the
  final word. Do not fill every available second—visual breathing room matters.
- Speak naturally and deliberately. Do not read filenames, headings, or timing
  notes aloud.
- Keep each scene in its own take. A mistake then costs one short recording,
  rather than a new four-minute performance.
- Copy the approved recordings to
  `../composition/assets/vo/seg1.wav` through `seg6.wav`.

Scene 3 remains one uninterrupted picture take, but its narration is still a
separate audio recording. Scene 4's callouts are visual prompts, not substitute
narration; read the complete scene-4 script.
