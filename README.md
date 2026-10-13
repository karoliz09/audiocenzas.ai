# AudioCenzas.ai

AudioCenzas.ai finds swear words in audio and video files and hides them. You can beep them, mute them or cut them out.

Everything runs on your own computer. Nothing is uploaded anywhere.

It is made mainly for Lithuanian, but it also knows common Russian and English swear words. Other languages work too if you add your own words to the list.

## What it can do

- Listens to your file and finds swear words automatically
- Shows a list of found words with their times (`h:mm:ss`)
- Lets you choose what to do with each word:
  - 🔔 **Beep** - a beep plays over the word
  - 🔇 **Mute** - the word becomes silent
  - ✂️ **Cut out** - the part is removed from the sound and the video
  - ⏭️ **Skip** - the word stays as it is
- Click a word's action in the list to change it, or change all words at once
- Click any other part of a row to hear that word
- Shows the full text of what was said. Click a word in the text to change its action, or to add a word the app missed
- Hover over a word to see what its icon means
- Shows how long the analysis took
- Interface in English or Lithuanian
- Uses an NVIDIA graphics card if you have one (faster), otherwise the normal processor
- Can also be used from the command line

## What you need

- Windows (the easy way), or Python 3.12+ on any system
- [ffmpeg](https://ffmpeg.org/) - `start.bat` installs it for you
- Optional: an NVIDIA graphics card for faster work

## How to install

**Windows (easy way):**

1. Download the project (**Code → Download ZIP**) and unzip it.
2. Double-click `start.bat`.

The first start takes a while: it installs everything it needs and opens the app in your browser.

**Manual way:**

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r src/requirements.txt
python src/app.py
```

The speech recognition model is downloaded the first time you use it.

## How to use

1. Open your audio or video file.
2. Choose the spoken language, the model and the default action.
3. Click **Analyze** and wait.
4. Check the list. Change actions, listen to words, add missed ones.
5. Click **Export**. The new file is saved in the `output/` folder.

### Command line

```bash
python src/audiocenzas.py input.mp4 [-o output.mp4] [--mode mute|beep|cut] [--lang lt] [--model small] [--words profanity.txt]
```

Here one action (`--mode`) is used for all words.

## Word list

The words to look for are in `profanity.txt`, one word per line:

- `*` means "any letters", e.g. `blyat*` also finds `blyatj`
- Lithuanian letters don't matter: `sudas` also finds `šūdas`
- Lines starting with `#` are notes and are ignored

Be careful with very short words. They can match normal words by mistake.

## Models

A bigger model is more accurate, but slower.

| Model | Speed | Accuracy |
|-------|-------|----------|
| `tiny`, `base` | fastest | low |
| `small` | default without a graphics card | medium |
| `medium` | slower | good |
| `large-v3` | default with a graphics card | best |

## Good to know

- Speech recognition is not perfect. Sometimes it writes a swear word differently, softens it, or uses Russian letters, so the word can be missed. Always check the list before exporting.
- Word times are not exact, so 0.15 s is added before and after each word.
- **Cut out** takes longer, because the video has to be processed again.
- Only the first sound track is kept in the new file.

## License

[MIT](LICENSE) - anyone can use, change and share it for free.
