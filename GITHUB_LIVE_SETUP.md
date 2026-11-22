# Publish VA AILOCK AI Studio on GitHub Pages

## What you get immediately
- Public editor at `https://YOUR_GITHUB_USERNAME.github.io/va-ailock-ai-studio/`
- Live browser-only Character Lab with adjustable face, pose, outfit colors and 4K PNG export
- Image upload, in-session scene library, and timeline planning
- No GPU or paid hosting for the static site

**Not included on GitHub Pages:** Python backend, model inference, actual AI generation, FFmpeg MP4 render, server image storage. The website does not pretend to do those tasks.

## Automatic GitHub publishing (recommended for Windows)

1. Extract the project ZIP into a normal folder (not directly inside the ZIP viewer). You can open `OPEN_LOCAL_PREVIEW.bat` to see the browser editor before publishing.
2. Double-click **SETUP_AND_PUBLISH.bat**. It installs Git/GitHub CLI via `winget` if needed, then opens GitHub CLI's browser sign-in when required.
3. The script creates a public `va-ailock-ai-studio` repository (or updates that exact repository), commits approved source files, pushes to `main`, and attempts to configure GitHub Pages from `/docs` automatically.
4. Check the deployment result in your new repository's **Actions** tab. The published site URL will be `https://YOUR_USERNAME.github.io/va-ailock-ai-studio/`.

**Safety:** The script never uploads `.env`, model checkpoints, or your user-generated art and it never force-pushes. It refuses to publish if `origin` points to a different GitHub repository. Your ChatGPT GitHub connection is distinct from the CLI login on your own computer.

## Publish in GitHub manually
1. Create a GitHub repository named `va-ailock-ai-studio`.
2. Upload the **contents** of the folder containing this file (so `docs/index.html` is at the path `docs/index.html`). Do not upload model weights, secrets, `.env`, or personal artwork to a public repository.
3. Open the repository **Settings > Pages**.
4. Set **Build and deployment > Deploy from a branch**; choose **main** and folder **/docs**, then save.
5. Wait for GitHub to provide the Pages link. Open it and select **Character Lab** to test 4K PNG export.

## Enable hosted AI image generation later
GitHub is source control and static hosting, **not** an inference GPU. Deploy a model elsewhere, e.g. an authenticated GPU machine running ComfyUI plus the included Python FastAPI server behind HTTPS (and a trusted authentication/reverse-proxy layer). The local FastAPI example is NOT production-hardened; do not expose it directly on the public Internet.

A production deployment needs authentication, HTTPS, per-user isolation, rate limiting, bounded generation queues, persistent private storage, secure upload handling, and CORS allowing your exact GitHub Pages origin. Model licenses and GPU hosting fees also apply.

Once a backend is securely deployed, enter its base HTTPS URL in the website's **Optional AI Backend** field. Do not put private credentials, API tokens, model checkpoints, or `.env` values in `docs/` or the public GitHub repository.

## Local backend
You can still run `app.py` on your Windows laptop following the original README. The included local server interface is at `http://127.0.0.1:8000`. A publicly hosted HTTPS page cannot reliably/safely connect to a private localhost server. Do not forward raw Ollama/ComfyUI/API ports directly to the Internet.

## Known limits
- Browser-only image uploads and timeline items are in-memory and cleared on refresh; download your PNGs.
- MP4 export and scene generation are intentionally unavailable until a protected backend is deployed.
- Entering a backend URL alone does not create hosting or make a GPU model available. Without CORS and auth, the connection will fail; this is expected.
- To replace the basic rig with a consistent custom 2D style model, train a permitted SDXL LoRA separately and load it on the GPU host.
