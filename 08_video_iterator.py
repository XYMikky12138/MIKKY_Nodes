import os
import cv2
import torch
import numpy as np
import imageio
import torchaudio
import subprocess
import tempfile
import shutil

# --- 1. 获取 FFmpeg 路径 (核心依赖) ---
try:
    from imageio_ffmpeg import get_ffmpeg_exe

    FFMPEG_PATH = get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = shutil.which("ffmpeg")

# 检查 FFmpeg 是否可用
if FFMPEG_PATH is None:
    print("\n[Warning] FFmpeg not found! Audio operations will fail.\n")

# --- 辅助函数 ---
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.webm', '.mkv', '.gif')


def get_video_files(folder_path):
    if not os.path.isdir(folder_path):
        return []
    files = []
    for f in os.listdir(folder_path):
        if f.lower().endswith(VIDEO_EXTENSIONS):
            files.append(os.path.join(folder_path, f))
    files.sort()
    return files


# --- 节点 1: 统计数量 ---
class MIKKYFolderVideoCount:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"folder_path": ("STRING", {"default": ""})}}

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("count", "folder_path")
    FUNCTION = "count_videos"
    CATEGORY = "MIKKY nodes/Video Iterator"

    def count_videos(self, folder_path):
        files = get_video_files(folder_path)
        return (len(files), folder_path)


# --- 节点 2: 快速获取信息 ---
class MIKKYVideoInfoByIndex:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "folder_path": ("STRING", {"default": ""}),
            "video_index": ("INT", {"default": 1, "min": 1})
        }}

    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("full_path", "filename", "filename_no_ext")
    FUNCTION = "get_info"
    CATEGORY = "MIKKY nodes/Video Iterator"

    def get_info(self, folder_path, video_index):
        files = get_video_files(folder_path)
        idx = video_index - 1
        if idx < 0 or idx >= len(files): raise ValueError(f"Index out of bounds.")
        video_path = files[idx]
        filename = os.path.basename(video_path)
        filename_no_ext = os.path.splitext(filename)[0]
        return (video_path, filename, filename_no_ext)


# --- 节点 3: 从路径加载视频 (修复音频加载逻辑) ---
class MIKKYLoadVideoFromPath:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "video_path": ("STRING", {"default": "", "forceInput": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO")
    RETURN_NAMES = ("images", "audio")
    FUNCTION = "load_video"
    CATEGORY = "MIKKY nodes/Video Iterator"

    def load_video(self, video_path):
        if not os.path.exists(video_path):
            raise ValueError(f"File not found: {video_path}")

        print(f"--- Loading Video: {os.path.basename(video_path)} ---")

        # 1. 读取视频画面
        cap = cv2.VideoCapture(video_path)
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame = frame.astype(np.float32) / 255.0
            frame = torch.from_numpy(frame)
            frames.append(frame)
        cap.release()

        if not frames: raise ValueError("No frames read.")
        video_tensor = torch.stack(frames)

        # 2. 读取音频 (强制使用 FFmpeg 提取 wav 中转)
        # 初始化空音频
        empty_audio = {"waveform": torch.zeros((1, 1, 1)), "sample_rate": 44100}
        audio_output = empty_audio

        if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
            temp_wav = None
            try:
                # 创建临时文件路径
                fd, temp_wav = tempfile.mkstemp(suffix=".wav")
                os.close(fd)

                # 使用 FFmpeg 提取音频
                # -vn: 禁用视频
                # -acodec pcm_s16le: 转为标准 wav 编码，torchaudio 最容易读取
                # -ar 44100: 强制采样率，避免兼容性问题 (可选，去掉则保持原采样率)
                # -y: 覆盖
                cmd = [FFMPEG_PATH, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", temp_wav]

                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

                # 读取生成的 wav
                if os.path.exists(temp_wav) and os.path.getsize(temp_wav) > 0:
                    waveform, sample_rate = torchaudio.load(temp_wav)

                    # 确保格式符合 ComfyUI 标准: (1, Channels, Samples)
                    if waveform.dim() == 2:  # (C, N)
                        waveform = waveform.unsqueeze(0)  # -> (1, C, N)

                    audio_output = {"waveform": waveform, "sample_rate": sample_rate}
                    print(f"DEBUG: Audio Loaded. Shape: {waveform.shape}, Rate: {sample_rate}")
                else:
                    print("DEBUG: Extracted audio file is empty or missing.")

            except Exception as e:
                print(f"DEBUG: Audio extraction failed: {e}")
            finally:
                if temp_wav and os.path.exists(temp_wav):
                    os.remove(temp_wav)
        else:
            print("DEBUG: FFmpeg not found, skipping audio load.")

        return (video_tensor, audio_output)


# --- 节点 4: 保存视频 (增强音频保存的鲁棒性) ---
class MIKKYSaveVideoToFolder:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "folder_path": ("STRING", {"default": "output/videos"}),
                "filename_prefix": ("STRING", {"default": "video"}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 0.01}),
                "overwrite": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "audio": ("AUDIO",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("saved_path",)
    FUNCTION = "save_video"
    CATEGORY = "MIKKY nodes/Video Iterator"
    OUTPUT_NODE = True

    def save_wav_robust(self, path, waveform, sample_rate):
        """
        一个鲁棒的 WAV 保存函数，尝试多种后端，避免 Torchaudio 报错
        """
        # 确保 waveform 是 (Channels, Samples) 或 (Samples,) 的 numpy 数组
        if isinstance(waveform, torch.Tensor):
            waveform = waveform.detach().cpu()
            if waveform.dim() == 3:  # (Batch, Channels, Samples)
                waveform = waveform.squeeze(0)
            waveform_np = waveform.numpy()
        else:
            waveform_np = waveform

        # 尝试 1: 使用 soundfile 直接保存 (最稳健，不依赖 torchaudio 复杂的 backend 机制)
        try:
            import soundfile as sf
            # soundfile 期望格式通常是 (Samples, Channels)，所以可能需要转置
            if waveform_np.ndim == 2 and waveform_np.shape[0] < 10:
                # 假设第一维是声道数 (例如 2xN)，soundfile 需要 Nx2
                waveform_np_t = waveform_np.T
            else:
                waveform_np_t = waveform_np

            sf.write(path, waveform_np_t, sample_rate)
            print("DEBUG: Saved audio using 'soundfile' library directly.")
            return True
        except ImportError:
            pass  # 没有安装 soundfile
        except Exception as e:
            print(f"DEBUG: soundfile write failed: {e}")

        # 尝试 2: 使用 scipy.io.wavfile (ComfyUI 环境通常都有 scipy)
        try:
            import scipy.io.wavfile
            # scipy 同样期望 (Samples, Channels)
            if waveform_np.ndim == 2 and waveform_np.shape[0] < 10:
                waveform_np_t = waveform_np.T
            else:
                waveform_np_t = waveform_np

            scipy.io.wavfile.write(path, sample_rate, waveform_np_t)
            print("DEBUG: Saved audio using 'scipy.io.wavfile'.")
            return True
        except ImportError:
            pass
        except Exception as e:
            print(f"DEBUG: scipy write failed: {e}")

        # 尝试 3: 回退到 torchaudio.save (尝试强制指定 backend)
        try:
            # 重新转回 Tensor，因为 torchaudio 需要 Tensor
            if not isinstance(waveform, torch.Tensor):
                waveform = torch.from_numpy(waveform)

            # 尝试指定 soundfile 后端
            torchaudio.save(path, waveform, sample_rate, backend="soundfile")
            print("DEBUG: Saved audio using torchaudio (backend='soundfile').")
            return True
        except Exception as e:
            print(f"DEBUG: torchaudio save with backend='soundfile' failed: {e}")

        # 尝试 4: torchaudio 默认保存 (最后挣扎)
        try:
            torchaudio.save(path, waveform, sample_rate)
            print("DEBUG: Saved audio using torchaudio (default).")
            return True
        except Exception as e:
            print(f"DEBUG: All audio save methods failed. Last error: {e}")
            return False

    def save_video(self, images, folder_path, filename_prefix, fps, overwrite, audio=None):
        print(f"--- Saving Video: {filename_prefix} ---")

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        filename = f"{filename_prefix}.mp4"
        output_path = os.path.join(folder_path, filename)

        if not overwrite:
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(folder_path, f"{filename_prefix}_{counter:04d}.mp4")
                counter += 1

        frames_np = (images.cpu().numpy() * 255).astype(np.uint8)

        temp_dir = tempfile.mkdtemp()
        temp_video = os.path.join(temp_dir, "temp_video.mp4")
        temp_audio = os.path.join(temp_dir, "temp_audio.wav")

        try:
            # 1. 保存纯视频
            # 修改 SaveVideoToFolder 类中的 imageio.mimwrite 部分
            imageio.mimwrite(
                temp_video,
                frames_np,
                fps=fps,
                codec='libx264',
                quality=None,
                macro_block_size=None,
                pixelformat='yuv420p',
                format='FFMPEG',
                # 新增下面这行：使用 ultrafast 预设和 CRF 控制质量
                ffmpeg_params=["-preset", "ultrafast", "-crf", "23"]
            )
            
            # 2. 检查音频并保存
            has_audio = False
            if audio is not None:
                waveform = audio.get("waveform")
                sample_rate = audio.get("sample_rate")

                if waveform is not None and waveform.numel() > 0:
                    # 调用新的鲁棒保存函数
                    if self.save_wav_robust(temp_audio, waveform, sample_rate):
                        has_audio = True
                    else:
                        print("DEBUG: Failed to save audio file, video will be silent.")

            # 3. 合并
            if has_audio and FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
                # 增加 -shortest 防止长度不一致
                cmd = [
                    FFMPEG_PATH, '-y',
                    '-i', temp_video,
                    '-i', temp_audio,
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-c:v', 'copy',
                    '-c:a', 'aac',
                    '-shortest',
                    output_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode != 0:
                    print(f"DEBUG: FFmpeg merge failed: {res.stderr.decode()}")
                    shutil.move(temp_video, output_path)
                else:
                    print("DEBUG: Merge successful.")
            else:
                shutil.move(temp_video, output_path)
                if has_audio: print("DEBUG: Audio ignored (ffmpeg issue).")

        except Exception as e:
            raise RuntimeError(f"Error saving video: {e}")
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        return (output_path,)


# --- 旧节点同步更新 (保持不变，因为调用了上面的类) ---
class MIKKYLoadVideoByIndex:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "folder_path": ("STRING", {"default": ""}),
            "video_index": ("INT", {"default": 1, "min": 1}),
        }}

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("images", "audio", "filename", "full_path", "filename_no_ext")
    FUNCTION = "load_video"
    CATEGORY = "MIKKY nodes/Video Iterator"

    def load_video(self, folder_path, video_index):
        info_node = MIKKYVideoInfoByIndex()
        full_path, filename, filename_no_ext = info_node.get_info(folder_path, video_index)
        loader_node = MIKKYLoadVideoFromPath()
        images, audio = loader_node.load_video(full_path)
        return (images, audio, filename, full_path, filename_no_ext)


# --- 注册节点 ---
NODE_CLASS_MAPPINGS = {
    "MIKKYFolderVideoCount": MIKKYFolderVideoCount,
    "MIKKYVideoInfoByIndex": MIKKYVideoInfoByIndex,
    "MIKKYLoadVideoFromPath": MIKKYLoadVideoFromPath,
    "MIKKYSaveVideoToFolder": MIKKYSaveVideoToFolder,
    "MIKKYLoadVideoByIndex": MIKKYLoadVideoByIndex
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYFolderVideoCount": "MIKKY Folder Video Count",
    "MIKKYVideoInfoByIndex": "MIKKY Video Info By Index",
    "MIKKYLoadVideoFromPath": "MIKKY Load Video From Path",
    "MIKKYSaveVideoToFolder": "MIKKY Save Video To Folder",
    "MIKKYLoadVideoByIndex": "MIKKY Load Video By Index"
}

