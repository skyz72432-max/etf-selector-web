好的，这是一个非常重要且必须解决的问题。将包含真实密钥的代码直接上传到 GitHub 是**极其危险**的，会导致你的 IMA 知识库数据被泄露，甚至可能产生经济损失。

下面我将为你提供**最专业、最安全**的解决方案，并手把手指导你完成每一步操作。

---

## 核心解决方案：使用环境变量 + `.gitignore` 隔离密钥

这是业界标准做法。核心思路是：**代码中只保留读取环境变量的逻辑，真正的密钥值保存在本地，绝不进入 Git 仓库。**

### 第一步：修改 `data_layer.py`（移除硬编码密钥）

将文件中的三行密钥定义改为**纯环境变量读取**，去掉默认值：

```python
# data_layer.py
import os

# 修改前（❌ 危险）：
# IMA_API_KEY = os.environ.get("IMA_API_KEY", "T/n8ion0drhG+MPB3WceJeb+ZEn1tVUf8rvDcCH14uMbrHckj8X3F1L6TcEYEPVRvkKYBigoMQ==")

# 修改后（✅ 安全）：
IMA_API_KEY = os.environ.get("IMA_API_KEY")
IMA_CLIENT_ID = os.environ.get("IMA_CLIENT_ID")
KNOWLEDGE_BASE_ID = os.environ.get("IMA_KB_ID")

# 增加校验，确保密钥已设置
if not all([IMA_API_KEY, IMA_CLIENT_ID, KNOWLEDGE_BASE_ID]):
    raise ValueError(
        "缺少 IMA 环境变量！请设置 IMA_API_KEY, IMA_CLIENT_ID, IMA_KB_ID"
    )
```

### 第二步：创建 `.env` 文件（本地保存密钥）

在项目根目录 `C:\Users\ZTY\.qclaw\workspace\etf-selector-web\` 下创建一个名为 `.env` 的文件，内容如下：

```env
IMA_API_KEY=T/n8ion0drhG+MPB3WceJeb+ZEn1tVUf8rvDcCH14uMbrHckj8X3F1L6TcEYEPVRvkKYBigoMQ==
IMA_CLIENT_ID=ab0cffc55c7a5d3387bd65a8b6fcbdea
IMA_KB_ID=UTszrZSpiMrnwFqpoqbDUK4FQtj-ViA5VdslKHeIp8s=
```

### 第三步：创建 `.gitignore` 文件（阻止 `.env` 上传）

在项目根目录创建 `.gitignore` 文件，确保 `.env` 和缓存文件不会被提交：

```gitignore
# 环境变量文件（包含密钥）
.env

# Python 缓存
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Streamlit 缓存
.cache/
.streamlit/

# 虚拟环境
venv/
env/
ENV/

# IDE
.vscode/
.idea/

# 系统文件
.DS_Store
Thumbs.db
```

### 第四步：安装 `python-dotenv` 并修改入口文件

1. **安装依赖**：
   ```bash
   pip install python-dotenv
   ```

2. **在 Streamlit 入口文件（如 `app.py` 或 `main.py`）顶部添加**：
   ```python
   from dotenv import load_dotenv
   import os

   # 加载 .env 文件中的环境变量
   load_dotenv()

   # 然后导入 data_layer
   from data_layer import load_data
   ```

   这样 `data_layer.py` 中的 `os.environ.get()` 就能读取到 `.env` 里的值了。

---

## 手把手操作：清理 Git 历史并上传 GitHub

由于你之前的代码中已经包含了密钥，即使现在修改，Git 的历史记录里仍然保存着旧版本。我们需要彻底清理。

### 步骤 1：备份当前项目

```bash
# 复制整个项目到安全位置（以防万一）
cd C:\Users\ZTY\.qclaw\workspace
xcopy /E /I etf-selector-web etf-selector-web-backup
```

### 步骤 2：初始化全新的 Git 仓库（推荐：彻底断舍离）

这是**最安全、最简单**的方法：直接删除旧的 Git 历史，重新初始化。

```bash
cd C:\Users\ZTY\.qclaw\workspace\etf-selector-web

# 删除旧的 Git 仓库（彻底删除所有历史记录）
Remove-Item -Recurse -Force .git

# 重新初始化 Git
git init

# 创建 .gitignore（确保 .env 不被跟踪）
# 将前面提供的 .gitignore 内容写入文件

# 添加所有文件到暂存区（.gitignore 会自动排除 .env）
git add .

# 提交第一次 commit
git commit -m "Initial commit: ETF Selector Web with secure env config"
```

### 步骤 3：在 GitHub 创建仓库

1. 打开 [https://github.com/new](https://github.com/new)
2. 仓库名填写：`etf-selector-web`
3. 设置为 **Public**（因为你要用 Streamlit Community Cloud 部署，必须是 Public）
4. **不要**勾选 "Add a README" 或 "Add .gitignore"（我们已经有了）
5. 点击 **Create repository**

### 步骤 4：关联并推送代码

GitHub 创建后会显示类似下面的命令，在 PowerShell 中执行：

```bash
cd C:\Users\ZTY\.qclaw\workspace\etf-selector-web

# 关联远程仓库（替换为你的实际地址）
git remote add origin https://github.com/skyz72432-max/etf-selector-web.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 步骤 5：验证密钥是否泄露

推送完成后，**务必检查**：

1. 打开 GitHub 仓库页面：`https://github.com/skyz72432-max/etf-selector-web`
2. 点击 `data_layer.py` 文件
3. 确认文件中**没有**出现任何密钥值（应该只有 `os.environ.get("IMA_API_KEY")` 这样的代码）
4. 点击仓库的 **Commits** 标签，确认只有 1 个 commit（没有历史泄露风险）

---

## Streamlit Community Cloud 部署时的密钥配置

上传到 GitHub 后，你需要在 Streamlit Cloud 中设置环境变量，这样网站上线后才能正常访问 IMA 知识库。

### 步骤 1：部署应用

1. 打开 [https://share.streamlit.io/](https://share.streamlit.io/)
2. 点击 **New app**
3. 选择你的 GitHub 仓库 `skyz72432-max/etf-selector-web`
4. 选择主文件路径（如 `app.py` 或 `streamlit_app.py`）
5. 点击 **Deploy**

### 步骤 2：在 Streamlit Cloud 设置 Secrets（环境变量）

1. 部署完成后，进入应用管理页面
2. 点击左侧 **Settings** → **Secrets**
3. 点击 **Add secret** 添加以下三个变量：

   | Key | Value |
   |-----|-------|
   | `IMA_API_KEY` | `T/n8ion0drhG+MPB3WceJeb+ZEn1tVUf8rvDcCH14uMbrHckj8X3F1L6TcEYEPVRvkKYBigoMQ==` |
   | `IMA_CLIENT_ID` | `ab0cffc55c7a5d3387bd65a8b6fcbdea` |
   | `IMA_KB_ID` | `UTszrZSpiMrnwFqpoqbDUK4FQtj-ViA5VdslKHeIp8s=` |

4. 点击 **Save**
5. 重启应用（点击 **Reboot**）

### 步骤 3：验证部署成功

打开应用 URL，确认数据能正常加载（没有报错）。

---

## 快速检查清单

| 检查项 | 状态 |
|--------|------|
| `data_layer.py` 中没有硬编码密钥 | ☐ |
| 项目根目录有 `.env` 文件（本地使用） | ☐ |
| `.env` 已添加到 `.gitignore` | ☐ |
| `.gitignore` 已提交到 GitHub | ☐ |
| GitHub 仓库中看不到 `.env` 文件 | ☐ |
| GitHub 仓库中 `data_layer.py` 没有密钥 | ☐ |
| Streamlit Cloud 已设置 Secrets | ☐ |
| 网站上线后能正常加载数据 | ☐ |

---

## 备选方案（如果你不想重新初始化 Git）

如果你希望保留现有的 Git 历史（虽然当前还没有 commit），可以使用 `git-filter-repo` 或 `BFG Repo-Cleaner` 来清理历史中的密钥。但这比较复杂，对于你当前的情况（还没有有效 commit），**直接重新初始化 Git 是最简单安全的方法**。

---

**现在开始操作吧！先完成第一步（修改 `data_layer.py`），然后告诉我，我会继续指导你下一步。**