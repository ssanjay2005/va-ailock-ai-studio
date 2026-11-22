"""Prepare captioned, user-owned artwork for SDXL LoRA imagefolder training.

Place picture.png and picture.txt (caption) side by side in a source folder.
Then run: python train/prepare_dataset.py --source my_art --output datasets/va_ailock
"""
import argparse
import json
import shutil
from pathlib import Path
from PIL import Image


def main():
    p = argparse.ArgumentParser(description='Build a Hugging Face imagefolder dataset')
    p.add_argument('--source', type=Path, required=True, help='Folder with image + same-name .txt captions')
    p.add_argument('--output', type=Path, required=True, help='Empty dataset output directory')
    args = p.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        p.error('Input source folder does not exist')
    if source == output or source in output.parents or output in source.parents:
        p.error('Source and output must be distinct, non-nested folders')
    supported = {'.jpg','.jpeg','.png','.webp'}
    files = sorted(x for x in source.iterdir() if x.is_file() and x.suffix.lower() in supported)
    if not files:
        p.error('No image files found in source')
    if output.exists() and list(output.iterdir()):
        p.error('Output already exists and is not empty; choose a new folder')
    output.mkdir(parents=True, exist_ok=True)
    lines=[]
    for i, im in enumerate(files, start=1):
        capfile=im.with_suffix('.txt')
        if not capfile.exists():
            p.error(f'Missing caption {capfile.name}. Add a detailed English caption first.')
        cap=capfile.read_text(encoding='utf-8').strip()
        if len(cap)<8:
            p.error(f'Caption too short in {capfile.name}')
        try:
            with Image.open(im) as picture:
                picture.verify()
            with Image.open(im) as picture:
                if min(picture.size)<512:
                    print(f'Warning: low resolution ({picture.size}) for {im.name}')
        except Exception:
            p.error(f'Invalid image: {im.name}')
        name=f'cartoon_{i:04d}{im.suffix.lower()}'
        shutil.copy2(im,output/name)
        lines.append({'file_name':name,'text':cap})
    with (output/'metadata.jsonl').open('w',encoding='utf-8') as f:
        for record in lines:
            f.write(json.dumps(record,ensure_ascii=False)+'\n')
    print(f'Prepared {len(lines)} captioned images in {output}')
    if len(files)<20:
        print('Note: fewer than 20 examples. Style training may be weak; quality and diversity matter.')


if __name__=='__main__': main()
