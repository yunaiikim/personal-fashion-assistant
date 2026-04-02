# -*- coding: utf-8 -*-
"""
专业形象顾问提示词生成器
  - 身材分析 (骨架量感×线条曲直理论方向)
  - 肤色分析 (四季色彩理论方向)
  - 个人风格识别 (PCCS色彩×Kibbe身形理论方向)
功能：将用户数据自动填充至标准分析提示词模版
"""

import os
import re
import base64
import io
import shutil
import sys
import tempfile
from PIL import Image

# ==============================================================================
# 1. 通用工具函数
# ==============================================================================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_prompt_template(filename: str) -> str:
    """读取同目录下的提示词模版文件"""
    filepath = os.path.join(_BASE_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

# ==============================================================================
# 2. 身材分析提示词
# ==============================================================================

# 身材参数默认值（缺失时显示为"-"）
BODY_DEFAULT_DATA = {
    "height": "-",
    "weight": "-",
    "shoulder_width": "-",
    "bust": "-",
    "waist": "-",
    "hip": "-",
    "wrist": "-",
    "leg_circumference": "-",
    "leg_length": "-",
    "body_features": "-"
}

def generate_consultant_prompt(user_data: dict) -> str:
    """
    生成填充后的身材形象顾问提示词

    参数:
        user_data (dict): 用户身体数据字典，键名需匹配 BODY_DEFAULT_DATA 中的键
                          例：{'height': '165cm', 'weight': '50kg'}

    返回:
        str: 填充完整的提示词字符串
    """
    final_data = BODY_DEFAULT_DATA.copy()
    if user_data:
        final_data.update(user_data)

    prompt_template = _load_prompt_template("body_data_prompt.md")
    try:
        filled_prompt = prompt_template.format(**final_data)
    except KeyError as e:
        print(f"[警告] 数据键名缺失：{e}，已自动替换为默认值")
        for key in BODY_DEFAULT_DATA.keys():
            if key not in final_data:
                final_data[key] = "-"
        filled_prompt = prompt_template.format(**final_data)

    return filled_prompt

# ==============================================================================
# 3. 肤色分析提示词
# ==============================================================================

# 肤色参数键列表（无默认值，缺失则删除该行）
SKIN_PARAM_KEYS = [
    "hair_color",        # 发色
    "pupil_color",       # 瞳孔色
    "face_tone",         # 自然光下面部色调
    "cheek_redness",     # 脸颊是否易泛红
    "skin_gloss",        # 肤质光泽感
    "vein_color",        # 血管测试结果
    "paper_test",        # 白纸测试结果
    "dress_preference",  # 日常穿搭偏好
    "visual_improvement" # 希望改善的视觉问题
]

def generate_skin_prompt(user_data: dict) -> str:
    """
    生成填充后的肤色形象顾问提示词

    逻辑：
      - 用户提供的参数 → 填入对应占位符
      - 用户未提供的参数 → 删除包含该占位符的整行

    参数:
        user_data (dict): 用户肤色数据字典
                          例：{'hair_color': '自然黑', 'vein_color': '蓝紫'}

    返回:
        str: 填充完整的提示词字符串（缺失项已被删除）
    """
    user_data = user_data or {}
    prompt_template = _load_prompt_template("skin_data_prompt.md")

    # 找出未提供的参数键
    missing_keys = [k for k in SKIN_PARAM_KEYS if k not in user_data]

    # 删除包含未提供参数占位符的整行
    result = prompt_template
    for key in missing_keys:
        # 匹配包含 {key} 的整行（含行首空白和换行符）
        result = re.sub(r'[ \t]*.*\{' + key + r'\}.*\n?', '', result)

    # 填充已提供的参数
    try:
        result = result.format(**user_data)
    except KeyError as e:
        print(f"[警告] 肤色数据键名缺失：{e}")

    # 清理连续空行（删除行后可能产生）
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result

# ==============================================================================
# 4. 个人风格识别提示词
# ==============================================================================

# 风格参数键列表（可选参数，缺失则删除该行）
STYLE_PARAM_KEYS = [
    "photo_count",        # 照片数量（由代码自动计算）
    "outfit_scenes",      # 穿搭常用场景
    "preferred_materials", # 偏好材质
    "avoided_items"        # 避雷单品
]

def save_uploaded_photos(file_data_list: list) -> dict:
    """
    将前端上传的照片保存到临时文件夹

    参数:
        file_data_list (list): 前端上传的文件数据列表，每个元素为 dict：
            {
                'filename': str,   # 原始文件名，如 'outfit1.jpg'
                'content': bytes   # 文件二进制内容
            }

    返回:
        dict: {
            'status': str,           # 'success' 或 'error'
            'temp_dir': str,         # 临时文件夹路径
            'temp_photo_paths': list # 保存后的文件路径列表
        }
    """
    if not file_data_list:
        return {"status": "error", "message": "未接收到任何照片文件"}

    temp_dir = tempfile.mkdtemp(prefix="style_photos_")
    temp_photo_paths = []

    for i, file_info in enumerate(file_data_list):
        filename = file_info.get("filename", f"upload_{i + 1}.jpg")
        content = file_info.get("content", b"")
        if not content:
            print(f"[警告] 第 {i + 1} 张照片内容为空，已跳过")
            continue

        # 统一重命名：outfit_1.jpg, outfit_2.png ...
        ext = os.path.splitext(filename)[1] or ".jpg"
        dst_name = f"outfit_{i + 1}{ext}"
        dst_path = os.path.join(temp_dir, dst_name)

        with open(dst_path, "wb") as f:
            f.write(content)
        temp_photo_paths.append(dst_path)

    if not temp_photo_paths:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return {"status": "error", "message": "所有照片内容均为空，保存失败"}

    return {
        "status": "success",
        "temp_dir": temp_dir,
        "temp_photo_paths": temp_photo_paths
    }


def _compress_and_encode_image(image_path: str, max_size=1024, quality=85) -> str:
    """
    图片预压缩 + Base64 编码，返回 Data URI

    流程（与 wardrobe_tools.py build_model_payload 保持一致）：
        1. 缩放至 max_size × max_size 以内
        2. 转为 JPEG（quality=85）
        3. Base64 编码 → Data URI
    """
    img = Image.open(image_path)
    img.thumbnail((max_size, max_size))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    pure_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{pure_base64}"


def build_style_payload(temp_photo_paths: list, user_data: dict = None,
                        model: str = "MiniMax-M2.7",
                        max_tokens: int = 2000) -> dict:
    """
    构建个人风格识别的 MiniMax 多模态模型请求 payload

    流程：
        1. 读取 self_style_prompt.md 模板并填充参数（缺失项删除对应行）
        2. 对每张照片执行预压缩（1024×1024 thumbnail → JPEG q=85）+ Base64 编码
        3. 组装 MiniMax 兼容的多图 payload dict

    参数:
        temp_photo_paths (list): 临时文件夹中的照片路径列表
                                 （由 save_uploaded_photos() 返回）
        user_data (dict):        可选参数字典
                                 例：{'outfit_scenes': '通勤/休闲',
                                      'preferred_materials': '棉麻/丝绸'}
        model (str):             模型名称（默认 MiniMax-M2.7）
        max_tokens (int):        最大输出 token 数（默认 2000）

    返回:
        dict: {
            'status': str,    # 'success' 或 'error'
            'payload': dict,  # MiniMax 请求 payload（仅 success 时）
            'prompt': str     # 填充后的提示词文本（仅 success 时）
        }
    """
    user_data = user_data or {}
    if not temp_photo_paths:
        return {"status": "error", "message": "照片列表为空，无法构建 payload"}

    # --- 1. 构建提示词 ---
    fill_data = user_data.copy()
    fill_data["photo_count"] = str(len(temp_photo_paths))

    prompt_template = _load_prompt_template("self_style_prompt.md")
    missing_keys = [k for k in STYLE_PARAM_KEYS if k not in fill_data]
    result = prompt_template
    for key in missing_keys:
        result = re.sub(r'[ \t]*.*\{' + key + r'\}.*\n?', '', result)

    try:
        result = result.format(**fill_data)
    except KeyError as e:
        print(f"[警告] 风格数据键名缺失：{e}")

    result = re.sub(r'\n{3,}', '\n\n', result)

    # --- 2. 图片预压缩 + Base64 编码 ---
    content_parts = [{"type": "text", "text": result}]

    for photo_path in temp_photo_paths:
        if not os.path.isfile(photo_path):
            print(f"[警告] 照片路径不存在，已跳过：{photo_path}")
            continue
        try:
            data_uri = _compress_and_encode_image(photo_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri}
            })
        except Exception as e:
            print(f"[警告] 照片编码失败({photo_path}): {e}")
            continue

    if len(content_parts) < 2:
        return {"status": "error", "message": "所有照片编码均失败，无法构建 payload"}

    # --- 3. 组装 MiniMax payload ---
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content_parts
            }
        ],
        "max_tokens": max_tokens,
    }

    return {"status": "success", "payload": payload, "prompt": result}


def cleanup_style_temp(temp_dir: str):
    """
    清理风格识别的临时照片文件夹（获取大模型结果后调用）

    参数:
        temp_dir (str): save_uploaded_photos() 返回的临时文件夹路径
    """
    if temp_dir and os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"[信息] 已清理临时照片文件夹：{temp_dir}")


# ==============================================================================
# 5. 评估充分性检查 & 评估 Payload 构建
# ==============================================================================

# 各类别必填字段定义
_REQUIRED_FIELDS = {
    "body": {
        "must":  ["height", "weight"],
        "preferred": ["shoulder_width", "bust", "waist", "hip", "wrist"],
        "min_preferred": 3,   # 至少提供 3 个可选围度
        "description": "身材分析"
    },
    "skin": {
        "must":  ["hair_color", "pupil_color", "face_tone"],
        "preferred": ["vein_color", "paper_test", "cheek_redness", "skin_gloss"],
        "min_preferred": 1,   # 至少一项测试结果
        "description": "肤色诊断"
    },
    "style": {
        "must":  [],           # 风格分析的核心输入是照片
        "preferred": ["outfit_scenes", "preferred_materials", "avoided_items"],
        "min_preferred": 0,
        "min_photos": 3,       # 至少 3 张 OOTD 照片
        "description": "风格识别"
    }
}


def check_data_sufficiency(category: str, user_data: dict,
                           photo_count: int = 0) -> dict:
    """
    检查指定类别的用户数据是否满足触发大模型评估的最低要求

    参数:
        category (str):    "body" / "skin" / "style"
        user_data (dict):  当前已收集的用户数据
        photo_count (int): 用户已上传的照片数量（仅 style 类别使用）

    返回:
        dict: {
            'ready':   bool,    # True=可触发评估
            'missing': list,    # 缺少的必填字段名
            'message': str      # 面向 Agent 的提示信息
        }
    """
    if category not in _REQUIRED_FIELDS:
        return {"ready": False, "missing": [],
                "message": f"未知类别：{category}，有效值为 body/skin/style"}

    spec = _REQUIRED_FIELDS[category]
    user_data = user_data or {}

    # 检查必填字段
    missing_must = [k for k in spec["must"] if k not in user_data or not user_data[k]]
    if missing_must:
        return {
            "ready": False,
            "missing": missing_must,
            "message": f"【{spec['description']}】缺少必填信息：{', '.join(missing_must)}，请继续引导用户提供。"
        }

    # 检查可选字段达标数量
    provided_preferred = [k for k in spec["preferred"] if k in user_data and user_data[k]]
    if len(provided_preferred) < spec["min_preferred"]:
        still_need = spec["min_preferred"] - len(provided_preferred)
        candidates = [k for k in spec["preferred"] if k not in user_data or not user_data[k]]
        return {
            "ready": False,
            "missing": candidates[:still_need],
            "message": f"【{spec['description']}】建议至少再补充 {still_need} 项：{', '.join(candidates[:still_need])}。"
        }

    # 风格类别额外检查照片数
    if category == "style":
        min_photos = spec.get("min_photos", 3)
        if photo_count < min_photos:
            return {
                "ready": False,
                "missing": [],
                "message": f"【{spec['description']}】照片不足，当前 {photo_count} 张，至少需要 {min_photos} 张 OOTD 照片。"
            }

    return {
        "ready": True,
        "missing": [],
        "message": f"【{spec['description']}】数据充分，可以触发大模型评估。"
    }


def build_body_eval_payload(user_data: dict,
                            model: str = "MiniMax-M2.7",
                            max_tokens: int = 2000) -> dict:
    """
    构建身材评估的 MiniMax 模型请求 payload（纯文本，无图片）

    流程：
        1. 调用 generate_consultant_prompt() 获取填充后的身材分析提示词
        2. 组装 MiniMax 兼容的纯文本 payload

    参数:
        user_data (dict):  用户身体数据
        model (str):       模型名称（默认 MiniMax-M2.7）
        max_tokens (int):  最大输出 token 数（默认 2000）

    返回:
        dict: {
            'status':   'success' / 'error',
            'payload':  dict,   # MiniMax 请求 payload（仅 success 时）
            'prompt':   str,    # 填充后的提示词文本（仅 success 时）
            'category': 'body'
        }
    """
    prompt = generate_consultant_prompt(user_data)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
    }

    return {"status": "success", "payload": payload,
            "prompt": prompt, "category": "body"}


def build_skin_eval_payload(user_data: dict,
                            model: str = "MiniMax-M2.7",
                            max_tokens: int = 2000) -> dict:
    """
    构建肤色评估的 MiniMax 模型请求 payload（纯文本，无图片）

    流程：
        1. 调用 generate_skin_prompt() 获取填充后的四季色彩诊断提示词
        2. 组装 MiniMax 兼容的纯文本 payload

    参数:
        user_data (dict):  用户肤色数据
        model (str):       模型名称（默认 MiniMax-M2.7）
        max_tokens (int):  最大输出 token 数（默认 2000）

    返回:
        dict: {
            'status':   'success' / 'error',
            'payload':  dict,
            'prompt':   str,
            'category': 'skin'
        }
    """
    prompt = generate_skin_prompt(user_data)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
    }

    return {"status": "success", "payload": payload,
            "prompt": prompt, "category": "skin"}


def build_evaluation_payload(category: str, user_data: dict,
                             photo_paths: list = None,
                             model: str = "MiniMax-M2.7",
                             max_tokens: int = 2000) -> dict:
    """
    统一评估入口：根据类别路由到对应的 payload 构建函数

    使用流程（Agent 侧）：
        1. 先调用 check_data_sufficiency() 确认 ready=True
        2. 调用本函数获取 payload
        3. 发送 payload 至大模型 API 获取评估结果
        4. 将评估结果展示给用户

    参数:
        category (str):       "body" / "skin" / "style"
        user_data (dict):     当前已收集的用户数据
        photo_paths (list):   照片路径列表（仅 style 类别使用）
        model (str):          模型名称
        max_tokens (int):     最大输出 token 数

    返回:
        dict: {
            'status':   'success' / 'error',
            'payload':  dict,
            'prompt':   str,
            'category': str
        }
    """
    if category == "body":
        return build_body_eval_payload(user_data, model, max_tokens)
    elif category == "skin":
        return build_skin_eval_payload(user_data, model, max_tokens)
    elif category == "style":
        if not photo_paths:
            return {"status": "error", "message": "风格评估需要照片路径列表",
                    "category": "style"}
        result = build_style_payload(photo_paths, user_data, model, max_tokens)
        if result["status"] == "success":
            result["category"] = "style"
        return result
    else:
        return {"status": "error",
                "message": f"未知评估类别：{category}，有效值为 body/skin/style",
                "category": category}


# ==============================================================================
# 6. 主程序入口 (演示用法)
# ==============================================================================
if __name__ == "__main__":
    # --- 身材分析演示 ---
    print("=" * 40)
    print("【身材分析】完整数据输入")
    print("=" * 40)
    body_data = {
        "height": "165cm",
        "weight": "50kg",
        "shoulder_width": "42cm",
        "bust": "70cm",
        "waist": "65cm",
        "hip": "73cm",
        "wrist": "14cm",
        "leg_circumference": "22cm",
        "leg_length": "101cm",
        "body_features": "侧面身体较薄、锁骨明显"
    }
    prompt_body = generate_consultant_prompt(body_data)
    print(prompt_body[:500])
    print("\n... (内容省略)\n")

    # --- 肤色分析演示 ---
    print("=" * 40)
    print("【肤色分析】部分数据输入（缺失项自动删除）")
    print("=" * 40)
    skin_data = {
        "hair_color": "自然黑",
        "pupil_color": "深棕带金边",
        "face_tone": "暖黄调",
        "vein_color": "蓝绿",
    }
    prompt_skin = generate_skin_prompt(skin_data)
    print(prompt_skin[:800])
    print("\n... (内容省略)\n")

    # --- 个人风格识别演示 ---
    print("=" * 40)
    print("【风格识别】模拟前端上传 → 保存 → 构建 Payload")
    print("=" * 40)

    # Step 1: 模拟前端上传照片（实际使用时 content 为真实文件二进制数据）
    mock_uploads = [
        {"filename": "ootd_1.jpg", "content": b"\xff\xd8\xff\xe0fake_jpeg_data_1"},
        {"filename": "ootd_2.png", "content": b"\x89PNG\r\n\x1a\nfake_png_data_2"},
    ]
    save_result = save_uploaded_photos(mock_uploads)
    print(f"保存结果: {save_result['status']}")
    print(f"临时目录: {save_result.get('temp_dir', 'N/A')}")
    print(f"照片列表: {save_result.get('temp_photo_paths', [])}")

    # Step 2: 构建 payload（此处因 mock 数据非真实图片，编码会失败，仅展示流程）
    style_data = {
        "outfit_scenes": "通勤/休闲",
        "preferred_materials": "棉麻/丝绸",
        # avoided_items 未提供 → 对应行将被删除
    }
    payload_result = build_style_payload(
        save_result.get("temp_photo_paths", []),
        style_data
    )
    print(f"Payload 构建状态: {payload_result['status']}")
    if payload_result["status"] == "success":
        print(f"Payload model: {payload_result['payload']['model']}")
        print(f"Content parts 数量: {len(payload_result['payload']['messages'][0]['content'])}")
        print(f"提示词预览:\n{payload_result['prompt'][:500]}")

    # Step 3: 模拟获取大模型结果后清理临时文件
    cleanup_style_temp(save_result.get("temp_dir", ""))
    print("\n... (内容省略)\n")

    # =================================================================
    # 评估充分性检查 & 评估 Payload 构建 演示
    # =================================================================
    print("=" * 40)
    print("【评估充分性检查】")
    print("=" * 40)

    # 身材 - 数据不足
    body_partial = {"height": "165cm"}
    check1 = check_data_sufficiency("body", body_partial)
    print(f"身材（仅身高）: ready={check1['ready']}, missing={check1['missing']}")
    print(f"  → {check1['message']}")

    # 身材 - 数据充足
    check2 = check_data_sufficiency("body", body_data)
    print(f"身材（完整数据）: ready={check2['ready']}")
    print(f"  → {check2['message']}")

    # 肤色 - 数据充足
    check3 = check_data_sufficiency("skin", skin_data)
    print(f"肤色（含血管测试）: ready={check3['ready']}")
    print(f"  → {check3['message']}")

    # 风格 - 照片不足
    check4 = check_data_sufficiency("style", style_data, photo_count=1)
    print(f"风格（1张照片）: ready={check4['ready']}")
    print(f"  → {check4['message']}")

    # 风格 - 照片充足
    check5 = check_data_sufficiency("style", style_data, photo_count=5)
    print(f"风格（5张照片）: ready={check5['ready']}")
    print(f"  → {check5['message']}")

    print("\n" + "=" * 40)
    print("【统一评估入口 - build_evaluation_payload】")
    print("=" * 40)

    # 身材评估 payload
    eval_body = build_evaluation_payload("body", body_data)
    print(f"身材评估: status={eval_body['status']}, category={eval_body['category']}")
    print(f"  payload model: {eval_body['payload']['model']}")
    print(f"  提示词前 200 字: {eval_body['prompt'][:200]}...")

    # 肤色评估 payload
    eval_skin = build_evaluation_payload("skin", skin_data)
    print(f"肤色评估: status={eval_skin['status']}, category={eval_skin['category']}")
    print(f"  payload model: {eval_skin['payload']['model']}")
    print(f"  提示词前 200 字: {eval_skin['prompt'][:200]}...")

    # 风格评估 payload（无照片路径 → error）
    eval_style_err = build_evaluation_payload("style", style_data)
    print(f"风格评估（无照片）: status={eval_style_err['status']}")
    print(f"  → {eval_style_err.get('message', '')}")

    print("\n✅ 评估模块演示完成")