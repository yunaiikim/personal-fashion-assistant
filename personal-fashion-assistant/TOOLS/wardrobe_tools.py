"""
SmartWardrobeArchiver Tools
===========================
基于 SmartWardrobeArchiver.md Skill 梳理出的工具集，
覆盖 初始化 → 图像预处理 → 模板加载 → 模型调用 → 交互确认 → 归档 → 异常处理 全流程。
"""

import os
import re
import shutil
import glob
import base64
import io
from datetime import datetime
from PIL import Image


class WardrobeManager:
    """智能衣橱归档管理器"""

    def __init__(self, base_dir="./smart_wardrobe", prompt_path=None):
        # ── 路径约定 ──
        self.base_dir = base_dir
        self.data_dir = os.path.join(self.base_dir, "wardrobe_data")
        self.temp_dir = os.path.join(self.base_dir, "temp_upload")
        self.inventory_file = os.path.join(self.base_dir, "inventory.md")
        self.prompt_path = prompt_path or os.path.join(
            ".", "PROMPT", "fashion_analyser_prompt.md"
        )

        # 为了兼容在TOOLS文件夹下直接运行的相对路径测试，加入智能回退
        if not os.path.exists(self.prompt_path):
            _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
            fallback = os.path.join(os.path.dirname(_SCRIPT_DIR), "PROMPT", "fashion_analyser_prompt.md")
            if os.path.exists(fallback):
                self.prompt_path = fallback

    # ================================================================
    # 1. Initialization（初始化）
    # ================================================================

    def init_environment(self):
        """
        【Skill §1 — Initialization】
        确保目录与索引文件就位。
        - 创建 wardrobe_data/ 和 temp_upload/ 目录
        - 若 inventory.md 不存在则创建并写入表头
        """
        for folder in [self.data_dir, self.temp_dir]:
            os.makedirs(folder, exist_ok=True)

        if not os.path.exists(self.inventory_file):
            with open(self.inventory_file, "w", encoding="utf-8") as f:
                f.write(
                    "| 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 |\n"
                )
                f.write(
                    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                )
            return {"status": "created", "message": "索引文件已创建并写入表头","inventory_file": os.path.abspath(self.inventory_file)}
        return {"status": "exists", "message": "环境已就绪，索引文件已存在", "inventory_file": os.path.abspath(self.inventory_file)}

    # ================================================================
    # 2. Image Processing（图像预处理 — Skill Step 1）
    # ================================================================

    def receive_image(self, source_image_path):
        """
        【Skill §2 Step 1 — Image Processing】
        接收用户上传的原始图片，统一重命名为 temp_processing[后缀]，
        并存入 ./smart_wardrobe/temp_upload/。
        返回临时文件路径供后续流程使用。
        """
        if not os.path.isfile(source_image_path):
            return {"status": "error", "message": f"源图片不存在: {source_image_path}"}

        file_ext = os.path.splitext(source_image_path)[1]
        temp_name = f"temp_processing{file_ext}"
        temp_path = os.path.join(self.temp_dir, temp_name)

        try:
            shutil.copy2(source_image_path, temp_path)
            return {"status": "success", "temp_path": temp_path}
        except Exception as e:
            return {"status": "error", "message": f"图片预处理失败: {str(e)}"}

    # ================================================================
    # 3. Template Loading（模板加载 — Skill Step 2）
    # ================================================================

    def load_prompt_template(self):
        """
        【Skill §2 Step 2 — Template Loading】
        从指定路径读取 fashion_analyser_prompt.md 作为 Prompt 文本。
        """
        if not os.path.isfile(self.prompt_path):
            return {
                "status": "error",
                "message": f"Prompt 模板文件未找到: {self.prompt_path}",
            }

        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            return {"status": "success", "prompt": prompt_text}
        except Exception as e:
            return {"status": "error", "message": f"模板读取失败: {str(e)}"}

    # ================================================================
    # 4. Payload Construction（Payload 构造 — Skill Step 3）
    # ================================================================

    def build_model_payload(self, prompt_text, image_path,
                            model="MiniMax-M2.7", max_tokens=800):
        """
        【Skill §2 Step 3 — Payload Construction】
        构造 MiniMax 多模态模型的请求 payload（不调用模型）。

        流程：
            1. 校验图片文件存在
            2. 图片预压缩（thumbnail 1024×1024 → JPEG quality=85）
            3. Base64 编码 → Data URI
            4. 组装并返回完整 payload dict

        参数:
            prompt_text : str  — Prompt 文本
            image_path  : str  — 图片文件路径
            model       : str  — 模型名称（默认 MiniMax-M2.7）
            max_tokens  : int  — 最大输出 token 数（默认 800）

        返回:
            {"status": "success", "payload": {…}} 或
            {"status": "error", "message": "…"}
        """
        if not os.path.isfile(image_path):
            return {"status": "error", "message": f"图片文件不存在: {image_path}"}

        try:
            # ── 图片预压缩，防止 Payload 过大导致 400 ──
            img = Image.open(image_path)
            img.thumbnail((1024, 1024))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)

            # ── Base64 编码 → Data URI ──
            pure_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            image_data_uri = f"data:image/jpeg;base64,{pure_base64}"

            # ── 组装 payload ──
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data_uri},
                            },
                        ],
                    }
                ],
                "max_tokens": max_tokens,
            }

            return {"status": "success", "payload": payload}
        except Exception as e:
            return {"status": "error", "message": f"Payload 构造失败: {str(e)}"}

    # ================================================================
    # 5. Interaction（交互确认 — Skill Step 4）
    # ================================================================

    def confirm_data(self, raw_output, user_input=None):
        """
        【Skill §2 Step 4 — Interaction】
        向用户展示模型返回的预览，根据指令决定下一步：
            - 确认/A   → 直接使用 raw_output
            - 重新生成/R → 返回 retry 信号
            - [Markdown] → 使用用户手动修改后的行

        参数:
            raw_output : str       — 模型原始输出
            user_input : str|None  — 用户输入；None 表示等待用户操作

        返回:
            action: "proceed" | "retry"
            final_data: 最终确认的 Markdown 数据（仅 proceed 时有值）
        """
        if user_input is None:
            return {
                "status": "pending",
                "preview": raw_output,
                "message": "请输入 [确认/A] 使用该数据，[重新生成/R] 重试，或直接粘贴修改后的 Markdown 行。",
            }

        cleaned = user_input.strip()
        if cleaned.upper() in ("确认", "A"):
            return {"status": "proceed", "final_data": raw_output}
        elif cleaned.upper() in ("重新生成", "R"):
            return {"status": "retry"}
        else:
            # 视为用户手动修改后的 Markdown 数据
            return {"status": "proceed", "final_data": cleaned}

    # ================================================================
    # 6. Archiving（归档动作 — Skill Step 5）
    # ================================================================

    def extract_item_id(self, markdown_row):
        """
        从 Markdown 表格行中通过正则提取 12 位衣物编号。
        匹配逻辑：查找第二个 | 之后、第三个 | 之前的 12 位字母数字。
        """
        match = re.search(r"\|[^|]+\|\s*([A-Z0-9]{12})\s*\|", markdown_row, re.IGNORECASE)
        return match.group(1) if match else None

    def check_id_conflict(self, item_id):
        """
        【Skill §3 — 编号冲突检测】
        检查 wardrobe_data/ 中是否已存在同名文件（不论扩展名）。
        """
        pattern = os.path.join(self.data_dir, f"{item_id}.*")
        return len(glob.glob(pattern)) > 0

    def _find_temp_image(self):
        """
        从 temp_upload/ 目录中自动定位临时图片文件。
        优先匹配 temp_processing.* 文件，否则取目录中第一个文件。
        返回: (图片路径, 错误信息) — 二者互斥
        """
        # 优先查找标准临时文件名
        for f in os.listdir(self.temp_dir):
            if f.startswith("temp_processing"):
                return os.path.join(self.temp_dir, f), None
        # 兜底：取目录中第一个文件
        all_files = [
            os.path.join(self.temp_dir, f)
            for f in os.listdir(self.temp_dir)
            if os.path.isfile(os.path.join(self.temp_dir, f))
        ]
        if all_files:
            return all_files[0], None
        return None, "temp_upload/ 目录中未找到临时图片，请先调用 receive_image() 上传图片。"

    def archive_item(self, markdown_data):
        """
        【Skill §2 Step 5 — Archiving（单行归档）】
        自动从 temp_upload/ 定位临时图片，对单行 Markdown 数据执行：
            1. 提取12位编号（含格式校验）
            2. 检测编号冲突
            3. 移动/重命名图片至 wardrobe_data/
            4. 追加索引至 inventory.md
        """
        # ── 定位临时图片 ──
        temp_image_path, err = self._find_temp_image()
        if err:
            return {"status": "error", "message": err}

        # ── 关键字段校验（Skill §3）──
        item_id = self.extract_item_id(markdown_data)
        if not item_id:
            return {
                "status": "error",
                "message": "检测到编号格式异常（需为12位字母数字），请修正后再次确认。",
            }

        # ── 编号冲突检测（Skill §3）──
        if self.check_id_conflict(item_id):
            return {
                "status": "conflict",
                "message": f"编号 {item_id} 已存在，请重新生成 ID 并更新表格行。",
                "item_id": item_id,
            }

        # ── 图片持久化 ──
        file_ext = os.path.splitext(temp_image_path)[1]
        final_image_path = os.path.join(self.data_dir, f"{item_id}{file_ext}")

        try:
            shutil.move(temp_image_path, final_image_path)
        except Exception as e:
            return {"status": "error", "message": f"图片保存失败（权限或路径异常）: {str(e)}"}

        # ── 追加索引 ──
        try:
            self._append_inventory(markdown_data)
            return {
                "status": "success",
                "item_id": item_id,
                "image_path": final_image_path,
            }
        except Exception as e:
            return {"status": "error", "message": f"索引文件写入失败: {str(e)}"}

    def archive_items_batch(self, markdown_data):
        """
        【Skill §2 Step 5 — Archiving（多行批量归档 + 清理）】
        自动从 temp_upload/ 定位临时图片，解析 Markdown 文本并逐行归档：
            - 单行：移动 (move) 临时图片
            - 多行：复制 (copy) 临时图片到每个编号，最后删除临时图片

        参数:
            markdown_data : str — 最终确认的 Markdown 表格行（可含多行）

        注意：自动过滤掉表头行和对齐行。
        """
        # ── 定位临时图片 ──
        temp_image_path, err = self._find_temp_image()
        if err:
            return {"status": "error", "message": err}

        lines = [
            line.strip()
            for line in markdown_data.strip().splitlines()
            if line.strip()
            and not line.strip().startswith("| :--")
            and not line.strip().startswith("| 分类")
        ]

        if not lines:
            return {"status": "error", "message": "未检测到有效的数据行"}

        results = []
        is_single = len(lines) == 1

        for idx, line in enumerate(lines):
            # ── 校验编号 ──
            item_id = self.extract_item_id(line)
            if not item_id:
                results.append({
                    "line": idx + 1,
                    "status": "error",
                    "message": "检测到编号格式异常（需为12位字母数字），请修正后再次确认。",
                })
                continue

            # ── 冲突检测 ──
            if self.check_id_conflict(item_id):
                results.append({
                    "line": idx + 1,
                    "status": "conflict",
                    "message": f"编号 {item_id} 已存在，请重新生成 ID。",
                    "item_id": item_id,
                })
                continue

            # ── 图片持久化 ──
            file_ext = os.path.splitext(temp_image_path)[1]
            final_image_path = os.path.join(self.data_dir, f"{item_id}{file_ext}")

            try:
                if is_single:
                    shutil.move(temp_image_path, final_image_path)
                else:
                    shutil.copy2(temp_image_path, final_image_path)
            except Exception as e:
                results.append({
                    "line": idx + 1,
                    "status": "error",
                    "message": f"图片保存失败: {str(e)}",
                    "item_id": item_id,
                })
                continue

            # ── 追加索引 ──
            try:
                self._append_inventory(line)
                results.append({
                    "line": idx + 1,
                    "status": "success",
                    "item_id": item_id,
                    "image_path": final_image_path,
                })
            except Exception as e:
                results.append({
                    "line": idx + 1,
                    "status": "error",
                    "message": f"索引写入失败: {str(e)}",
                    "item_id": item_id,
                })

        # ── 清理临时图片（Skill §2 Step 5 — Cleanup）──
        if not is_single and os.path.isfile(temp_image_path):
            try:
                os.remove(temp_image_path)
            except Exception:
                pass  # 清理失败不影响整体结果

        return {"status": "done", "results": results}

    # ================================================================
    # 7. Cleanup（清理 — Skill Step 5 尾部）
    # ================================================================

    def cleanup_temp(self):
        """
        【Skill §2 Step 5 — Cleanup】
        清空 temp_upload/ 目录中的所有临时文件。
        """
        removed = []
        for f in os.listdir(self.temp_dir):
            fp = os.path.join(self.temp_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)
                removed.append(f)
        return {"status": "success", "removed_files": removed}

    # ================================================================
    # 内部工具方法
    # ================================================================

    def _append_inventory(self, markdown_row):
        """向 inventory.md 追加一行数据，自动处理新文件场景。"""
        file_exists = os.path.exists(self.inventory_file)
        with open(self.inventory_file, "a", encoding="utf-8") as f:
            if not file_exists:
                f.write(
                    "| 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 |\n"
                )
                f.write(
                    "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                )
            f.write(markdown_row.strip() + "\n")

    def get_current_date(self):
        """获取当前日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")


# ====================================================================
# 测试代码
# ====================================================================

def _create_dummy_image(path):
    """创建一个模拟的 JPEG 图片文件用于测试"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0")  # 伪 JPEG 头部


def _print_section(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")


if __name__ == "__main__":
    import shutil as _shutil

    # 每次测试前清理旧数据，保证可重复运行
    if os.path.exists("./smart_wardrobe"):
        _shutil.rmtree("./smart_wardrobe")

    wm = WardrobeManager()

    # ──────────────────────────────────────────────
    # Test 1: 初始化环境
    # ──────────────────────────────────────────────
    _print_section("Test 1: 初始化环境")
    print(wm.init_environment())
    # 再次调用应返回 exists
    print(wm.init_environment())

    # ──────────────────────────────────────────────
    # Test 2: 单行归档 (archive_items_batch)
    # ──────────────────────────────────────────────
    _print_section("Test 2: 单行归档")
    # 模拟图片已通过 receive_image 存入 temp_upload
    _create_dummy_image("./smart_wardrobe/temp_upload/temp_processing.jpg")
    mock_md = "| 上衣 | TEST12345678 | 纯白T恤 | 白色 | 纯棉 | 极简 | 20°C | 春秋 | 休闲 | 2026-03-30 | 正常使用 |"
    result = wm.archive_items_batch(mock_md)
    print(f"归档结果: {result}")
    # 验证: wardrobe_data/ 下应有 TEST12345678.jpg
    assert os.path.isfile("./smart_wardrobe/wardrobe_data/TEST12345678.jpg"), "❌ 图片归档失败"
    print("✅ 图片已归档到 wardrobe_data/TEST12345678.jpg")

    # ──────────────────────────────────────────────
    # Test 3: 编号冲突检测
    # ──────────────────────────────────────────────
    _print_section("Test 3: 编号冲突")
    _create_dummy_image("./smart_wardrobe/temp_upload/temp_processing.jpg")
    conflict_md = "| 上衣 | TEST12345678 | 运动外套 | 黑色 | 涤纶 | 运动 | 15°C | 秋季 | 户外 | 2026-03-30 | 正常使用 |"
    result = wm.archive_items_batch(conflict_md)
    print(f"冲突结果: {result}")
    # 应该返回 conflict 状态
    assert result["results"][0]["status"] == "conflict", "❌ 未检测到编号冲突"
    print("✅ 编号冲突检测通过")

    # ──────────────────────────────────────────────
    # Test 4: 多行批量归档
    # ──────────────────────────────────────────────
    _print_section("Test 4: 多行批量归档")
    _create_dummy_image("./smart_wardrobe/temp_upload/temp_processing.jpg")
    multi_md = """| 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 上衣 | AABB11223344 | 藏青色衬衫 | 藏青色 | 纯棉 | 极简主义 | 18°C - 25°C | 春秋 | 日常工作 | 2026-03-30 | 正常使用 |
| 下装 | CCDD55667788 | 黑色西裤 | 黑色 | 羊毛混纺 | 商务 | 10°C - 20°C | 秋季 | 职场通勤 | 2026-03-30 | 闲置中 |"""
    result = wm.archive_items_batch(multi_md)
    print(f"批量归档结果: {result}")
    assert os.path.isfile("./smart_wardrobe/wardrobe_data/AABB11223344.jpg"), "❌ 第一件归档失败"
    assert os.path.isfile("./smart_wardrobe/wardrobe_data/CCDD55667788.jpg"), "❌ 第二件归档失败"
    # 多行模式下临时图片应被清理
    assert not os.path.isfile("./smart_wardrobe/temp_upload/temp_processing.jpg"), "❌ 临时图片未清理"
    print("✅ 多行归档 + 临时清理通过")

    # ──────────────────────────────────────────────
    # Test 5: 编号格式异常
    # ──────────────────────────────────────────────
    _print_section("Test 5: 编号格式异常")
    _create_dummy_image("./smart_wardrobe/temp_upload/temp_processing.jpg")
    bad_md = "| 上衣 | SHORT | 纯白T恤 | 白色 | 纯棉 | 极简 | 20°C | 春季 | 休闲 | 2026-03-30 | 正常使用 |"
    result = wm.archive_items_batch(bad_md)
    print(f"异常结果: {result}")
    assert result["results"][0]["status"] == "error", "❌ 未检测到编号格式异常"
    print("✅ 编号格式校验通过")

    # ──────────────────────────────────────────────
    # Test 6: temp_upload 无图片时归档
    # ──────────────────────────────────────────────
    _print_section("Test 6: 无临时图片")
    wm.cleanup_temp()  # 先清空
    result = wm.archive_items_batch(mock_md)
    print(f"无图片结果: {result}")
    assert result["status"] == "error", "❌ 未检测到缺少图片"
    print("✅ 无临时图片报错通过")

    # ──────────────────────────────────────────────
    # Test 7: 检查 inventory.md 内容
    # ──────────────────────────────────────────────
    _print_section("Test 7: 检查 inventory.md")
    with open("./smart_wardrobe/inventory.md", "r", encoding="utf-8") as f:
        content = f.read()
    print(content)
    assert "TEST12345678" in content, "❌ 索引中缺少 TEST12345678"
    assert "AABB11223344" in content, "❌ 索引中缺少 AABB11223344"
    assert "CCDD55667788" in content, "❌ 索引中缺少 CCDD55667788"
    print("✅ inventory.md 内容校验通过")

    # ──────────────────────────────────────────────
    # Test 8: cleanup_temp
    # ──────────────────────────────────────────────
    _print_section("Test 8: 清理临时目录")
    _create_dummy_image("./smart_wardrobe/temp_upload/leftover.png")
    result = wm.cleanup_temp()
    print(f"清理结果: {result}")
    assert len(os.listdir("./smart_wardrobe/temp_upload")) == 0, "❌ 清理不彻底"
    print("✅ cleanup_temp 通过")

    print(f"\n{'='*50}")
    print(" 🎉 全部测试通过！")
    print(f"{'='*50}")
