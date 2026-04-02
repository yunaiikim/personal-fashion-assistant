---
name: "smart_wardrobe_archiver"
description: 用于处理衣物图片的自动化入库、特征分析、编号生成及本地文件索引管理。

# 【版本与作者】
version: "1.0.0"
author: "Yuna"
---


# 0. Trigger Condition (触发条件)
当满足以下条件时，启动本 Skill (clothing_add)：
1. **安装引导**：在用户处于初始安装流程，被引导并选择进行首次入库时。
2. **冲突检查后**：用户执行完 `clothing_conflict_check` 冲突检查后，明确确认要将该衣物录入衣橱时。
3. **主动触发**：用户上传照片并附带诸如“入库”、“归档”、“纳入衣橱”、“加入衣柜”或“记录”等明确的录入指令。

> 🚨 **全局路由交互规则（针对仅上传照片的场景）**：
> 收到用户上传照片后，Agent **必须等待 10 秒**，看用户是否提出进一步意图。
> 若 10 秒后用户未提出意图，Agent 必须主动询问：“请问您是要进行**冲突检查**还是**入库**？” 根据用户回复触发相应技能。

# 1. Tool Binding (工具绑定)
本Skill依赖于 [wardrobe_tools.py](./TOOLS/wardrobe_tools.py) （位于 `./TOOLS/` 目录下）提供的 `WardrobeManager` 类。AI 在执行各步骤时可调用相应方法：
| 逻辑阶段 | 触发动作 | 调用工具方法 | 输入参数 | 预期输出 |
| :--- | :--- | :--- | :--- | :--- |
| 环境准备 | 首次启动/检测缺失 | `init_environment()` | 无 | 确认目录及文件已就绪 |
| 文件预处理 | 接收用户图片 | `receive_image()` | `image_file` (原始流) | 返回暂存路径及临时文件名 |
| 指令构建 | 准备分析请求 | `load_prompt_template()` | 无 | 返回 `fashion_analyser_prompt.md` 全文 |
| Payload 构造 | 准备模型请求体 | `build_model_payload()` | `prompt_text`, `image_path`, `model`(可选), `max_tokens`(可选) | 返回包含 Data URI 的完整请求 payload dict |
| 模型调用 | 发送 Payload 至 API | AI Agent 自行调用模型 API | `build_model_payload()` 返回的 `payload` | 返回 Markdown 表格行 |
| 数据持久化 | 用户确认入库 | `archive_items_batch()` | `final_md_string` | 返回处理结果（成功/失败/编号冲突） |
| 系统维护 | 流程结束 | `cleanup_temp()` | 无 | 清空 `temp_upload` 目录 |

# 2. Initialization (初始化步骤)
## 调用 init_environment()。

## Directory Check:
确保根目录 ./smart_wardrobe/ 存在。
建立图片仓库：./smart_wardrobe/wardrobe_data/ (用于持久化存储归档图片)。
建立临时缓存：./smart_wardrobe/temp_upload/ (用于存放用户刚上传、待确认的原始图片)。

## File Check:
检查索引数据库 ./smart_wardrobe/inventory.md。
若不存在：创建该文件并写入如下标准表头及对齐行：
| 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
若已存在：跳过创建，准备在末尾追加数据。

# 3. Execution Logic (执行逻辑)

> 🚨 **批量处理规则 (Batch Processing Rule)**：
> 如果用户一次性批量上传了多张图片，Agent必须对每张图片**逐一**串行执行完整的【Step 1 ~ Step 5】循环流程。
> 即：必须在当前图片完成预处理、模型解析、用户确认、入库归档及最后的 `cleanup_temp()` 清理后，才能开始处理下张图片。严禁同时调用工具预处理所有图片，否则会导致临时存储文件被覆盖。每张图片处理完成后，再进入下一张的处理流程。

## Step 1: Image Processing (图像预处理)
接收用户上传的原始图片，统一重命名为temp_processing[后缀]。
将其存入本地目录：./smart_wardrobe/temp_upload/。

## Step 2: Template Loading (模版加载):
模板加载 (Template Loading):
从 ./skills/wardrobe_manager/fashion_analyser_prompt.md 读取 Markdown 文本作为Prompt。

## Step 3: Payload Construction & Model Invocation (构造 Payload 与模型调用):
### Step 3a: 构造 Payload
调用 `build_model_payload(prompt_text, image_path)` ，工具层自动将图片预压缩、编码为 Data URI（`data:image/jpeg;base64,...`），并组装为 MiniMax 兼容的请求 payload dict。
### Step 3b: 调用模型
AI Agent 取得 payload 后，自行通过 HTTP 请求（或 SDK）发送至多模态大模型 API。
捕获 AI 返回的原始字符串，确保输出格式严格符合以下表头结构：
| 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |


## Step 4: Interaction (交互确认) - [CRITICAL BORDER]
* **状态标识**：进入 `WAIT_CONFIRM` 状态。
* **AI 行为限制**：
    * **必须暂停**：向用户展示 Markdown 预览后，AI **必须停止**所有自动化工具调用。
    * **严禁越权**：在收到“确认”、“A”或修改指令前，**禁止**调用 `archive_items_batch()`。
* **指令监听与分支**：
    * **信号 A（确认）**：仅当用户输入“确认”、“A”、“OK”时，状态转为 `EXECUTING`，跳转至 Step 5。
    * **信号 B（修改）**：若用户发送了包含 `|` 的表格行，更新内存中的数据，跳转至 Step 5。
    * **无信号**：保持静默，或在 30 秒后礼貌提醒用户确认。

## Step 5: Archiving (归档动作)

调用 archive_items_batch(final_md_string)
    工具端逻辑：
        提取 12 位 ID（若提取失败，工具返回 Error，AI 需提示用户修正）。
        自动处理单图移动或多图复制归档, 记录图片路径。
        自动追加数据至 inventory.md，需增加图片路径列，确保记录格式符合以下表头结构：
            | 分类 | 衣物编号 | 衣物名称 | 主要颜色 | 材质 | 风格 | 适宜的温度 | 推荐季节 | 适合的场景 | 当日日期 | 衣物状态 | 图片路径 |
            | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |

清理 (Cleanup)：调用 cleanup_temp()。

# 4. Error Handling (异常处理)
关键字段校验：在【Step 5 Archiving】开始前，必须验证Markdown行中是否存在合规的12位编号。
    处理：若因用户手动修改导致无法提取ID，应中断归档并提示：“检测到编号格式异常（需为12位字母数字），请修正后再次确认。”
编号冲突：如果生成的编号与现有文件名冲突，AI应重新生成ID并更新表格行。
权限问题：如果无法创建目录或写入文件，需及时向用户报错。

# 5. Constraint (约束)
严禁在未经用户确认的情况下直接修改 inventory.md。
每次入库操作必须以 cleanup_temp() 结尾，保证系统整洁。
