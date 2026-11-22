# Train a VA AILOCK 2D art-style LoRA

This guide sets up an **actual trainable model component** from your own images. Training is not automatic when you start the website. It requires CUDA-compatible training hardware, time, disk space, images you have rights to use, and a separately prepared environment.

## 1. Assemble captioned artwork

Make a folder `my_art` with files like:

```text
my_art/
  scene_001.png
  scene_001.txt
  scene_002.png
  scene_002.txt
  ...
```

Example `scene_001.txt`: `VA AILOCK style, original hand-drawn 2D Tamil cartoon, an ordinary young man sitting at a wooden desk in a modern Chennai apartment, surprised expression, clean dark ink outlines, warm earthy colors, medium shot`. Use consistent style phrases, but vary poses, expressions, backgrounds and framing. Do not include images you are not licensed to train on.

Prepare the `imagefolder` dataset using the included script:

```powershell
python train/prepare_dataset.py --source my_art --output datasets/va_ailock
```

It creates images + a `metadata.jsonl` file. Review the resulting captions before training.

## 2. Set up official Diffusers training

Follow the official [SDXL LoRA training guide](https://github.com/huggingface/diffusers/blob/main/examples/text_to_image/README_sdxl.md). Use a **separate** Python virtual environment because training dependencies are much larger than the web app's. Download the official examples:

```powershell
git clone https://github.com/huggingface/diffusers.git
cd diffusers
pip install -e .
cd examples/text_to_image
pip install -r requirements_sdxl.txt
accelerate config default
```

PyTorch GPU packages depend on your particular NVIDIA card, CUDA driver, and available VRAM; use PyTorch's platform-specific install instructions before training. The following is a starting command to adapt **after** reading the linked guide, not a guaranteed fit for every GPU.

```powershell
accelerate launch train_text_to_image_lora_sdxl.py --pretrained_model_name_or_path="stabilityai/stable-diffusion-xl-base-1.0" --train_data_dir="../../datasets/va_ailock" --caption_column="text" --resolution=768 --train_batch_size=1 --gradient_accumulation_steps=4 --gradient_checkpointing --max_train_steps=1000 --learning_rate=1e-4 --lr_scheduler="constant" --lr_warmup_steps=0 --mixed_precision="fp16" --output_dir="../../models/va_ailock_sdxl_lora" --report_to="none"
```

**Paths above are illustrative**: the dataset is normally outside `diffusers/`, so replace the relative `--train_data_dir` and `--output_dir` with correct *absolute* Windows paths. Low VRAM may need a lower resolution, 8-bit optimizer, or rented GPU. Always validate sample images to avoid overfitting. Output is usually named `pytorch_lora_weights.safetensors`.

## 3. Connect trained weights

1. Confirm output format / SDXL model compatibility with ComfyUI's LoraLoader; conversion may be required for certain Diffusers LoRA exports.
2. Copy compatible `.safetensors` LoRA to ComfyUI's `models/loras/` folder.
3. Set `COMFY_LORA=your_lora.safetensors` in the studio `.env` file, then restart the studio and ComfyUI (if needed).
4. Generate held-out prompts. A seed helps repeatability, but **does not** by itself lock characters, backgrounds or facial features. For that, add reference-image conditioning such as IP-Adapter/ControlNet in a later version.

**Do not assume commercial permissions**: check the base model license, dataset rights, LoRA release terms, and third-party checkpoint permissions. SDXL's license is listed on its official Hugging Face model card.
