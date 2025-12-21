# MIKKY Nodes 整合说明

本目录包含了所有ComfyUI插件的整合版本，所有节点都已统一添加MIKKY前缀，并归类到"MIKKY nodes"分类中。

## 文件列表

1. `01_average_split_node.py` - window frames平均分段计算节点
2. `02_batch_utils.py` - 批次工具节点（Stride、Fusion），用于图像的重叠（重叠后方便观察所有帧中水印遮罩的固定位置）
3. `03_frame_aligner.py` - 视频帧与音频同步节点，将视频输出帧率与音频帧率对齐
4. `05_imagejudge.py` - 图像尺寸限制节点（Lanczos）
5. `07_mask_batcher.py` - 遮罩批处理节点
6. `08_video_iterator.py` - 视频迭代器节点（搭配MIKKY Extract Storyboards节点使用）
7. `09_wan_image_viewer.py` - 图像查看选择器节点
8. `10_mask_editor.py` - 遮罩编辑器节点（视频遮罩编辑微调节点）
9. `11_banana_utils.py` - Banana局部重绘工具节点（Smart Crop、Uncrop Paste）
10. `12_extract_float.py` - 文本浮点数提取节点
11. `14_mikky_image.py` - 条件图像输入节点（若加载图像，则输出该图像，若不加载，则输出空值）
12. `15_video_seg.py` - 视频分段切片节点
13. `16_siliconflow_tagger.py` - SiliconFlow异步图像打标节点（支持并发和速率限制）
14. `17_split_options.py` - 音频分段切片节点
15. `18_image_resize_duplicate.py` - 图像批量缩放复制节点
16. `19_video_side_splitter.py` - 视频左右拆分节点
17. `20_storyboard_extractor.py` - 故事板提取节点（关键帧提取，支持图像和音频分析）
18. `21_savelogs.py` - 保存日志列表节点（将字符串列表保存为多个文本文件）
19. `22_load_images_from_folder.py` - 从文件夹加载图像节点（输出图像列表和文件名）

## 文件结构

```
MIKKY_Nodes/
├── __init__.py                    # Python节点自动加载文件
├── js/                            # JavaScript UI扩展文件
│   ├── __init__.js               # JS文件说明
│   ├── 01_mask_editor.js         # 遮罩编辑器UI
│   ├── 02_wan_image_viewer.js    # Wan图像查看器UI
│   └── 03_conditional_image_input.js  # 条件图像输入UI
├── 01_average_split_node.py      # Python节点文件
├── 02_batch_utils.py
├── ... (其他节点文件)
└── README.md                      # 本文件
```

## 使用方法

### 自动加载（推荐）

插件已配置为自动加载模式。`__init__.py` 文件会自动导入所有节点文件，无需手动整合。

**安装步骤：**
1. 将整个 `MIKKY_Nodes` 文件夹复制到 ComfyUI 的 `custom_nodes` 目录
2. 重启 ComfyUI
3. 所有节点将自动加载，可在节点菜单的 `MIKKY nodes` 分类下找到

**当前包含的节点数量：** 19 个节点文件，涵盖图像处理、视频处理、音频处理、遮罩编辑等多个功能领域。

### JS文件使用说明

JS文件位于 `js/` 目录下，用于增强某些节点的UI功能：

- `01_mask_editor.js` - 遮罩编辑器UI增强
- `02_wan_image_viewer.js` - Wan图像查看器UI
- `03_conditional_image_input.js` - 条件图像输入UI

`__init__.py` 中已设置 `WEB_DIRECTORY = "./js"`，ComfyUI会自动加载这些文件。

## 节点命名规则

- 所有节点类名都已添加 `MIKKY` 前缀
- 所有节点显示名都已添加 `MIKKY` 前缀
- 所有节点分类都统一为 `"MIKKY nodes"`，并进一步细分为子分类（如 `"MIKKY nodes/Utils"`、`"MIKKY nodes/Video Segment"` 等）

详细的节点分类列表请参考 [CATEGORIES.md](CATEGORIES.md)

## 注意事项

1. 确保所有依赖库已安装
2. 某些节点可能需要额外的依赖（如FFmpeg、VHS等）
3. 如果遇到导入错误，请检查相关依赖是否已安装

## 故障排除

### MIKKY Mask Editor 节点无法使用

如果MIKKY Mask Editor节点的UI无法正常显示，请检查：

1. **JS文件路径**：确保 `__init__.py` 中设置了 `WEB_DIRECTORY = "./js"`
2. **节点名称匹配**：Python和JS中的节点名称必须完全一致（`MIKKYMaskEditorNode`）
3. **浏览器控制台**：打开开发者工具查看是否有错误信息或调试日志

详细故障排除指南请参考 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

