**GitHub Pages deployment:** On Windows, extract and run `SETUP_AND_PUBLISH.bat` for guided repository creation and Pages setup. Alternatively see [GITHUB_LIVE_SETUP.md](GITHUB_LIVE_SETUP.md). Static website files are in `docs/`.

# VA AILOCK AI Studio (local starter)

A real, extensible starter for your own creative AI web app. This repository contains the website, a FastAPI backend, an integration with locally running ComfyUI image generation, optional Ollama chat/storyboards, a hand-editable SVG pose character, scene uploads, and an FFmpeg vertical video renderer. It **does not bundle pretrained foundation model weights** or misrepresent the starter as a trained custom model.

## Quick start on Windows

1. Install **Python 3.11 or 3.12** and **FFmpeg**, adding them to PATH. Python 3.13 may also work with current packages, but 3.11/3.12 is a conservative default. Verify with `ffmpeg -version` and `py --version` in PowerShell.
2. Extract folder and double-click `start_windows.bat`. Alternatively in PowerShell:
   ```powershell
   cd path\to\va_ailock_ai_studio
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app:app --host 127.0.0.1 --port 8000
   ```
3. Open <http://127.0.0.1:8000>. Even without an image model, you can edit a character in Pose Lab, export its PNG, upload scene images, arrange shots, and render MP4 with FFmpeg.
4. For *real AI image generation*, install and start [ComfyUI](https://github.com/Comfy-Org/ComfyUI). Download a **legally usable SDXL-compatible checkpoint** into `ComfyUI/models/checkpoints/`; verify the model's terms and suitability for your art. Copy `.env.example` to `.env`, set `COMFY_CHECKPOINT` to the **exact checkpoint filename**, and keep `COMFY_URL=http://127.0.0.1:8188`. Restart this server. Use Studio > Generate.
5. For the optional AI chat / storyboard planner, install [Ollama](https://ollama.com), pull a chat model suitable for your machine, and set `OLLAMA_MODEL` to exactly that model's local tag. Restart the studio. Without Ollama, the storyboard tool explicitly runs a fixed template (not AI).
6. To apply **your custom style LoRA** (trained separately), place the compatible LoRA in `ComfyUI/models/loras/`, set `COMFY_LORA=filename.safetensors` and optional `COMFY_LORA_STRENGTH=0.8` in `.env`, restart the server.

## What's real now, and what's planned

| Feature | Status |
|---|---|
| Prompt-to-image through a separately installed local checkpoint/ComfyUI | Implemented adapter |
| Optional user-owned style LoRA loading | Implemented adapter; train your own LoRA separately |
| Local Ollama writing assistant / AI storyboarding | Implemented adapter; requires model |
| Editable cartoon pose character + 2160x3840 PNG export | Implemented SVG Pose Lab |
| Scene images (AI or uploads) as storyboard/timeline | Implemented |
| Image-to-vertical-MP4 export, hard cuts, Ken Burns zoom | Implemented FFmpeg renderer |
| Optional voiceover and music tracks, music volume | Implemented |
| Full nonlinear multitrack editing, compositing, masking | Not built |
| ControlNet / IP-Adapter for shot-to-shot identity and pose consistency | Planned; required for stronger continuity |
| True character animation / lip sync / image-to-video model | Not built |
| Native AI image generation without external model weights | Impossible; connect a local model as documented |
| Native 4K *generative* image quality | Not assured; Pose Lab gives 4K SVG raster output and video renderer outputs 4K frames (upscaling is not detail creation) |

## Training your own VA AILOCK image model

The recommended first stage is **SDXL + LoRA**, not foundation-model training. Prepare a dataset you own/have permission to use: original 2D cartoon images and captions, with repeated characters drawn consistently in different expressions, angles, and locations. Keep separate character and style datasets when possible. Follow the official [Diffusers LoRA training guide](https://huggingface.co/docs/diffusers/training/lora) or [SDXL DreamBooth LoRA guide](https://huggingface.co/docs/diffusers/training/dreambooth). Training is **not** included in this minimal app because hardware requirements and training dataset need planning. Move the completed LoRA file into ComfyUI's LoRA folder. Fine-tuning does not ensure perfect identity across every shot; later integrate reference guidance + pose conditioning.

## Project layout

- `app.py`: local FastAPI app with ComfyUI, Ollama, FFmpeg endpoints.
- `static/`: dependency-free web interface with visual Pose Lab and video timeline.
- `data/assets/`: generated and uploaded images/audio.
- `data/exports/`: rendered MP4 files.
- `.env.example`: local model configuration.

## Notes and safety

- Local use only: binds to `127.0.0.1` by default; do not expose directly to the public Internet. No login/auth or resource quotas are implemented.
- Big models may run slowly or fail on limited VRAM. For laptops, test preview/768 generation first, and do 4K rendering only when needed.
- Keep input assets under 80MB each, 80 scenes max, 10 minutes max. Rendering is synchronous and blocks a worker; a task queue will be appropriate for larger projects.
- Image generation's ComfyUI `KSampler`, checkpoint, and encoder nodes assume an SDXL / standard Stable Diffusion checkpoint layout. FLUX or other model families require their own API workflows.
- Audio effects, auto subtitles, music beat synchronization, pose/character rigging beyond the one SVG figure, and image-to-video synthesis are future milestones.

## Basic diagnostics

- `GET http://127.0.0.1:8000/api/status` reports back-end connection status.
- For image errors, verify checkpoint name in ComfyUI and that it is running on port 8188.
- For render failures, verify `ffmpeg -version` in the terminal where you launch the app.
- The initial app exposes source files and can be customized, but it is an **MVP**, not an alternative to ChatGPT or a production-ready video editor.
