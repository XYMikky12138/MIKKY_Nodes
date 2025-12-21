import os
import torch
import numpy as np
from PIL import Image
from nodes import LoadImage
import folder_paths

# 特殊默认文件名
DEFAULT_WHITE_FILENAME = "_comfyui_default_white_512x512.png"


def ensure_default_white_image():
    input_dir = folder_paths.get_input_directory()
    default_path = os.path.join(input_dir, DEFAULT_WHITE_FILENAME)
    if not os.path.exists(default_path):
        img = Image.new('RGB', (512, 512), (255, 255, 255))
        img.save(default_path)
    return DEFAULT_WHITE_FILENAME


class MIKKYConditionalImageInput:
    def __init__(self):
        self.default_name = ensure_default_white_image()

    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = sorted(files)
        # 确保默认文件存在
        if DEFAULT_WHITE_FILENAME not in files:
            img = Image.new('RGB', (512, 512), (255, 255, 255))
            img.save(os.path.join(input_dir, DEFAULT_WHITE_FILENAME))
            files.append(DEFAULT_WHITE_FILENAME)
            files = sorted(files)

        return {
            "required": {
                "image": (files, {"default": DEFAULT_WHITE_FILENAME, "image_upload": True}),
                "reset_flag": ("BOOLEAN", {"default": False}),  # 用 BOOLEAN 模拟按钮
            },
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"
    CATEGORY = "MIKKY nodes/Image Input"
    DESCRIPTION = "默认显示白图。若用户未更改（仍为默认白图），输出空；若用户更换图片，则输出该图片。点击 Reset 按钮可恢复默认状态。"

    def load_image(self, image, reset_flag):
        # 如果 reset_flag 为 True，强制重置为默认白图
        if reset_flag:
            # 注意：这里我们不改变 image 的值，而是直接返回 None
            # 但为了让 UI 反映重置，我们需要在前端 JS 中真正设置 image 下拉框
            # 所以这里只做逻辑处理：返回 None
            return (None, None)

        # 正常逻辑：如果是默认白图，输出 None；否则加载图片
        if image == DEFAULT_WHITE_FILENAME:
            return (None, None)
        loader = LoadImage()
        return loader.load_image(image)

    @classmethod
    def IS_CHANGED(cls, image, reset_flag):
        # 如果 reset_flag 为 True，强制重新执行
        return reset_flag

    # 自定义 widget 渲染：将 reset_flag 渲染为按钮
    @classmethod
    def get_input_widget(cls, input_name, input_data):
        if input_name == "reset_flag":
            # 返回一个按钮，点击时设置 reset_flag 为 True，然后立即设为 False
            return """
            <button id="reset_btn_{node_id}" style="width:100%; padding:8px; background:#555; color:white; border:none; cursor:pointer;">
                Reset to Default White Image
            </button>
            <script>
            document.getElementById('reset_btn_{node_id}').addEventListener('click', function() {
                // 找到 reset_flag 输入框（通常是隐藏的 input[type=checkbox]）
                var checkbox = document.querySelector('[data-name="reset_flag"]');
                if (checkbox) {
                    checkbox.checked = true;
                    // 触发 change 事件
                    var event = new Event('change');
                    checkbox.dispatchEvent(event);

                    // 稍后自动取消勾选（模拟瞬时按钮）
                    setTimeout(function() {
                        checkbox.checked = false;
                        checkbox.dispatchEvent(new Event('change'));
                    }, 100);

                    // 同时重置 image 下拉框
                    var select = document.querySelector('[data-name="image"]');
                    if (select) {
                        select.value = "{default_filename}";
                        select.dispatchEvent(new Event('change'));
                    }
                }
            });
            </script>
            """.format(node_id="{node_id}", default_filename=DEFAULT_WHITE_FILENAME)


NODE_CLASS_MAPPINGS = {
    "MIKKYConditionalImageInput": MIKKYConditionalImageInput
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MIKKYConditionalImageInput": "MIKKY Conditional Image Input (with Reset Button)"
}

