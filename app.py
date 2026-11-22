"""VA AILOCK AI Studio: local creative workflow API.

This application does not pretend to contain model weights: ComfyUI supplies the
image model, Ollama optionally supplies an assistant, and FFmpeg renders video.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
ASSETS = DATA / 'assets'
EXPORTS = DATA / 'exports'
STATIC = ROOT / 'static'
for folder in (ASSETS, EXPORTS):
    folder.mkdir(parents=True, exist_ok=True)

# .env support with no mandatory extra dependency.
ENVFILE = ROOT / '.env'
if ENVFILE.exists():
    for line in ENVFILE.read_text(encoding='utf8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

COMFY_URL = os.environ.get('COMFY_URL', 'http://127.0.0.1:8188').rstrip('/')
COMFY_CHECKPOINT = os.environ.get('COMFY_CHECKPOINT', '').strip()
COMFY_LORA = os.environ.get('COMFY_LORA', '').strip()
COMFY_LORA_STRENGTH = float(os.environ.get('COMFY_LORA_STRENGTH', '0.8'))
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', '').strip()
FFMPEG = shutil.which('ffmpeg')
app = FastAPI(title='VA AILOCK AI Studio', version='0.1.0')
app.mount('/data', StaticFiles(directory=str(DATA)), name='data')
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

STYLE = ('professional 2D hand-drawn Indian comic and Tamil animated storytelling, '
         'expressive clean black outlines, painterly muted earthy colours, cinematic '
         'lighting, modern Chennai city life, consistent character design, strictly '
         'flat 2D animation artwork, no 3D, no photorealism, no anime, '
         'no text, no subtitles, no logo, no watermark, vertical 9:16 composition')
NEGATIVE = ('3d render, photorealism, anime, chibi, watermark, logo, text, '
            'typography, subtitles, malformed anatomy, extra limbs, ugly hands, blur')
ALLOWED_IMAGE = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_AUDIO = {'.wav', '.mp3', '.aac', '.m4a', '.ogg', '.flac'}
MAX_UPLOAD = 80 * 1024 * 1024


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    character: str = Field(default='PIXEL', max_length=180)
    expression: str = Field(default='surprised', max_length=100)
    pose: str = Field(default='standing', max_length=100)
    location: str = Field(default='modern Chennai room', max_length=200)
    camera: str = Field(default='medium shot', max_length=120)
    seed: int = Field(default=42, ge=0, le=2**63-1)
    steps: int = Field(default=25, ge=1, le=60)
    width: Literal[512, 768, 1024] = 768
    height: Literal[768, 1024, 1344, 1536] = 1344


class Scene(BaseModel):
    asset: str = Field(min_length=1, max_length=150)
    duration: float = Field(default=2.0, ge=0.4, le=20)
    motion: Literal['slow-zoom', 'static'] = 'slow-zoom'


class RenderRequest(BaseModel):
    scenes: list[Scene] = Field(min_length=1, max_length=80)
    resolution: Literal['preview', '1080p', '4k'] = '1080p'
    voice_asset: str | None = None
    music_asset: str | None = None
    music_volume: float = Field(default=0.12, ge=0, le=1)


class PlanRequest(BaseModel):
    story: str = Field(min_length=5, max_length=6000)
    count: int = Field(default=5, ge=2, le=12)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    history: list[dict] = Field(default_factory=list, max_length=12)


def safe_asset(value: str, kind: str | None = None) -> Path:
    # Never resolve arbitrary user paths.
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}\.(?:png|jpg|jpeg|webp|wav|mp3|aac|m4a|ogg|flac)', value):
        raise HTTPException(400, 'Invalid asset identifier')
    path = ASSETS / value
    if not path.is_file():
        raise HTTPException(404, f'Asset {value} not found')
    if kind == 'image' and path.suffix.lower() not in ALLOWED_IMAGE:
        raise HTTPException(400, 'This asset must be an image')
    if kind == 'audio' and path.suffix.lower() not in ALLOWED_AUDIO:
        raise HTTPException(400, 'This asset must be audio')
    return path


@app.get('/')
def homepage():
    return FileResponse(STATIC / 'index.html')


@app.get('/api/status')
def status():
    comfy_ok = False
    ollama_ok = False
    try:
        with httpx.Client(timeout=2) as c:
            comfy_ok = c.get(f'{COMFY_URL}/system_stats').status_code == 200
    except Exception:
        pass
    if OLLAMA_MODEL:
        try:
            with httpx.Client(timeout=2) as c:
                ollama_ok = c.get(f'{OLLAMA_URL}/api/tags').status_code == 200
        except Exception:
            pass
    return {'comfy_connected': comfy_ok, 'comfy_configured': bool(COMFY_CHECKPOINT),
            'ollama_connected': ollama_ok, 'ollama_model': OLLAMA_MODEL,
            'ffmpeg_connected': bool(FFMPEG), 'style': STYLE}


@app.get('/api/assets')
def list_assets():
    out = []
    for f in sorted(ASSETS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix.lower() in ALLOWED_IMAGE | ALLOWED_AUDIO:
            out.append({'asset': f.name, 'url': f'/data/assets/{f.name}',
                        'kind': 'image' if f.suffix.lower() in ALLOWED_IMAGE else 'audio'})
    return out[:150]


@app.post('/api/assets/upload')
async def upload_asset(file: UploadFile = File(...)):
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED_IMAGE | ALLOWED_AUDIO:
        raise HTTPException(400, 'Only PNG/JPG/WEBP and common audio files are supported')
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, 'File exceeds 80 MB')
    if ext in ALLOWED_IMAGE:
        # Validate the actual image, not just its filename.
        from PIL import Image
        import io
        try:
            with Image.open(io.BytesIO(content)) as im:
                im.verify()
        except Exception as exc:
            raise HTTPException(400, 'Invalid image file') from exc
    asset = f'{uuid.uuid4().hex[:20]}{ext}'
    (ASSETS / asset).write_bytes(content)
    return {'asset': asset, 'url': f'/data/assets/{asset}',
            'kind': 'image' if ext in ALLOWED_IMAGE else 'audio'}


def comfy_workflow(r: GenerateRequest):
    rich_prompt = (f'{r.prompt}. Main character: {r.character}. '
                   f'Facial expression: {r.expression}. Body pose: {r.pose}. '
                   f'Environment: {r.location}. Camera: {r.camera}. {STYLE}')
    workflow = {
        '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': COMFY_CHECKPOINT}},
        '5': {'class_type': 'EmptyLatentImage', 'inputs': {'batch_size': 1, 'width': r.width, 'height': r.height}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['4', 1], 'text': rich_prompt}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['4', 1], 'text': NEGATIVE}},
        '3': {'class_type': 'KSampler', 'inputs': {'model': ['4', 0], 'positive': ['6', 0],
              'negative': ['7', 0], 'latent_image': ['5', 0], 'seed': r.seed,
              'steps': r.steps, 'cfg': 6.5, 'sampler_name': 'euler', 'scheduler': 'normal', 'denoise': 1}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': ['4', 2]}},
        '9': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'VA_AILOCK', 'images': ['8', 0]}},
    }
    if COMFY_LORA:
        workflow['10'] = {'class_type': 'LoraLoader', 'inputs': {
            'lora_name': COMFY_LORA, 'strength_model': COMFY_LORA_STRENGTH,
            'strength_clip': COMFY_LORA_STRENGTH, 'model': ['4', 0], 'clip': ['4', 1]}}
        workflow['3']['inputs']['model'] = ['10', 0]
        workflow['6']['inputs']['clip'] = ['10', 1]
        workflow['7']['inputs']['clip'] = ['10', 1]
    return workflow


@app.post('/api/generate')
def generate_image(r: GenerateRequest):
    if not COMFY_CHECKPOINT:
        raise HTTPException(503, 'Set COMFY_CHECKPOINT in .env to an installed ComfyUI model file')
    try:
        with httpx.Client(timeout=15) as c:
            submit = c.post(f'{COMFY_URL}/prompt', json={'prompt': comfy_workflow(r),
                                                          'client_id': str(uuid.uuid4())})
            submit.raise_for_status()
            response = submit.json()
            prompt_id = response.get('prompt_id')
            if not prompt_id:
                raise HTTPException(502, f'ComfyUI rejected workflow: {str(response)[:500]}')
        deadline = time.monotonic() + 180
        with httpx.Client(timeout=20) as c:
            while time.monotonic() < deadline:
                h = c.get(f'{COMFY_URL}/history/{prompt_id}')
                h.raise_for_status()
                record = h.json().get(prompt_id)
                if record:
                    outputs = record.get('outputs', {})
                    images = outputs.get('9', {}).get('images', [])
                    if not images:
                        raise HTTPException(502, 'Generation ended without a saved image. Check the ComfyUI console.')
                    desc = images[0]
                    params = {'filename': desc['filename'], 'subfolder': desc.get('subfolder', ''),
                              'type': desc.get('type', 'output')}
                    img = c.get(f'{COMFY_URL}/view?{urlencode(params)}')
                    img.raise_for_status()
                    asset = f'{uuid.uuid4().hex[:20]}.png'
                    (ASSETS / asset).write_bytes(img.content)
                    return {'asset': asset, 'url': f'/data/assets/{asset}',
                            'prompt_id': prompt_id, 'seed': r.seed}
                time.sleep(1)
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise HTTPException(502, f'ComfyUI communication failed: {str(e)[:280]}') from e
    raise HTTPException(504, 'Generation timed out after 180 seconds; check ComfyUI history')


def chat_ollama(messages, schema=None):
    payload = {'model': OLLAMA_MODEL, 'messages': messages, 'stream': False,
               'options': {'temperature': 0.7}}
    if schema is not None:
        payload['format'] = schema
    with httpx.Client(timeout=90) as c:
        resp = c.post(f'{OLLAMA_URL}/api/chat', json=payload)
        resp.raise_for_status()
        return resp.json()['message']['content']


@app.post('/api/plan')
def plan_storyboard(r: PlanRequest):
    if OLLAMA_MODEL:
        schema = {'type': 'object', 'properties': {'title': {'type': 'string'},
          'scenes': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'prompt': {'type': 'string'}, 'duration': {'type': 'number'},
            'camera': {'type': 'string'}, 'expression': {'type': 'string'}},
            'required': ['prompt', 'duration', 'camera', 'expression']}}},
          'required': ['title', 'scenes']}
        try:
            s = chat_ollama([{'role':'system','content':(
              f'You are a Tamil 2D comedy storyboard director. Reply as JSON. Make exactly {r.count} '
              'short visual-first scenes. Fast pacing, no filler, hook in 2s, final punchline. '
              'Descriptions in English for image generation; no text drawn in images. '
              'Scene durations 1-5 seconds. Keep same character and location details.')},
              {'role':'user','content':r.story}], schema)
            raw = json.loads(s)
            scenes = raw.get('scenes', [])[:r.count]
            if scenes:
                return {'title':str(raw.get('title','Storyboard'))[:120],
                        'scenes':[{'prompt':str(x.get('prompt',''))[:600],
                          'duration':min(5,max(1,float(x.get('duration',2)))),
                          'camera':str(x.get('camera','medium shot'))[:100],
                          'expression':str(x.get('expression','animated'))[:100]}
                          for x in scenes], 'mode':'ollama'}
        except Exception:
            pass
    # Explicit non-AI fallback: usable draft, not masquerading as generated intelligence.
    beats = [f'Hook: {r.story[:240]}', 'Character spots an unexpected problem',
             'Character reacts and tries a clever solution',
             'The situation escalates in a funny visual moment',
             'Unexpected punchline reaction in a close-up']
    return {'title':'Manual starter storyboard', 'mode':'template',
            'scenes':[{'prompt':beats[i % len(beats)],
                       'duration':2.0, 'camera':'close-up' if i == r.count-1 else 'medium shot',
                       'expression':'shocked' if i == r.count-1 else 'expressive'}
                      for i in range(r.count)]}


@app.post('/api/assistant')
def assistant(r: ChatRequest):
    if not OLLAMA_MODEL:
        return {'reply':('The conversational AI is not configured yet. Install Ollama, download '
                 'a chat model, and set OLLAMA_MODEL in .env. The storyboard template, Pose Lab, '
                 'asset uploads and FFmpeg editing already work without Ollama.'),
                 'connected': False}
    system = {'role':'system','content':(
        'You are VA AILOCK Studio, an expert creative assistant for original Tamil comedy '
        'animated Shorts. Respond in clear English or Tanglish using Latin letters only. '
        'Advise on timing, scene prompts, continuity and sound design. No Tamil script. '
        'Do not pretend to generate images, render video, or change files in chat: tell the '
        'user which studio controls do that. Optimize 20-30 second, narrator-only videos.')}
    history = [{'role':x['role'], 'content':str(x['content'])[:1500]}
               for x in r.history if x.get('role') in {'user','assistant'} and 'content' in x]
    try:
        answer = chat_ollama([system, *history[-12:], {'role':'user','content':r.message}])
        return {'reply':answer, 'connected':True}
    except Exception as e:
        raise HTTPException(502, f'Ollama unavailable: {str(e)[:200]}') from e


def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=1000)
    if p.returncode:
        raise HTTPException(500, f'FFmpeg error: {p.stderr[-1300:]}')


@app.post('/api/video/render')
def render_video(r: RenderRequest):
    if not FFMPEG:
        raise HTTPException(503, 'FFmpeg not installed or absent from PATH')
    dimensions = {'preview':(540,960), '1080p':(1080,1920), '4k':(2160,3840)}
    width, height = dimensions[r.resolution]
    # Preserve a useful limit; UHD rendering is particularly expensive on laptops.
    total = sum(x.duration for x in r.scenes)
    if total > 600:
        raise HTTPException(400, 'Total video length must not exceed 10 minutes')
    images = [safe_asset(x.asset, 'image') for x in r.scenes]
    voice = safe_asset(r.voice_asset, 'audio') if r.voice_asset else None
    music = safe_asset(r.music_asset, 'audio') if r.music_asset else None
    output_name = f'VA_AILOCK_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4'
    output = EXPORTS / output_name
    with tempfile.TemporaryDirectory(prefix='va-ailock-') as td:
        tmp = Path(td)
        clips = []
        for i, (scene, asset) in enumerate(zip(r.scenes, images)):
            clip = tmp / f'clip_{i:03d}.mp4'
            if scene.motion == 'slow-zoom':
                # Ken Burns style enlargement (one zoompan output frame per input frame).
                sw, sh = int(width * 1.2), int(height * 1.2)
                vf = (f'scale={sw}:{sh}:force_original_aspect_ratio=increase,'
                      f'crop={sw}:{sh},setsar=1,'
                      f"zoompan=z='min(zoom+0.00075,1.16)':d=1:s={width}x{height}:fps=30,"
                      'format=yuv420p')
            else:
                vf = (f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                      f'crop={width}:{height},setsar=1,fps=30,format=yuv420p')
            run([FFMPEG, '-hide_banner', '-loglevel','error', '-y', '-loop', '1',
                 '-framerate','30', '-i', str(asset), '-t', str(scene.duration), '-vf', vf,
                 '-an', '-c:v','libx264', '-preset', 'veryfast', '-crf','21',
                 '-pix_fmt','yuv420p', '-r','30', '-movflags','+faststart', str(clip)])
            clips.append(clip)
        concat = tmp / 'list.txt'
        concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in clips), encoding='utf8')
        merged = tmp / 'merged.mp4'
        run([FFMPEG, '-hide_banner','-loglevel','error','-y','-f','concat',
             '-safe','0','-i',str(concat),'-c','copy',str(merged)])
        if not voice and not music:
            shutil.copyfile(merged, output)
        else:
            args = [FFMPEG,'-hide_banner','-loglevel','error','-y','-i',str(merged)]
            if voice:
                args.extend(['-i', str(voice)])
            if music:
                args.extend(['-stream_loop','-1','-i',str(music)])
            if voice and music:
                args.extend(['-filter_complex',
                  f'[1:a]volume=1,apad[v];[2:a]volume={r.music_volume},apad[m];'
                  '[v][m]amix=inputs=2:duration=first:dropout_transition=0[a]',
                  '-map','0:v:0','-map','[a]'])
            else:
                args.extend(['-map','0:v:0', '-map','1:a:0', '-af',
                             'apad' if voice else f'volume={r.music_volume},apad'])
            args.extend(['-c:v','copy','-c:a','aac','-b:a','192k',
                         '-t',str(total),'-movflags','+faststart',str(output)])
            run(args)
    return {'url':f'/data/exports/{output_name}', 'name':output_name,
            'seconds':round(total,2), 'resolution': f'{width}x{height}'}
