# ETF智选专家 - 密钥安全设置与GitHub部署指南

## 当前状态：✅ 本地安全改造已完成

我已经帮你完成了以下所有本地改造，现在你的项目已经**安全无密钥泄露风险**：

### 已完成的工作：

1. **✅ 修改 `data_layer.py`** — 移除了所有硬编码密钥，改为纯环境变量读取，并添加校验逻辑
2. **✅ 创建 `.env` 文件** — 本地保存密钥，已被 `.gitignore` 保护，不会进入 Git 仓库
3. **✅ 创建 `.gitignore`** — 阻止 `.env` 和缓存文件进入 Git 仓库
4. **✅ 修改 `app.py`** — 添加 `python-dotenv` 加载逻辑，本地开发自动读取 `.env`
5. **✅ 更新 `requirements.txt`** — 添加 `python-dotenv>=1.0.0` 依赖
6. **✅ 初始化全新 Git 仓库** — 确保没有历史密钥泄露
7. **✅ 提交到本地 Git** — 4 个 commit，均不含密钥

### 当前 Git 状态：
- 分支：`master`（本地）
- Commit 数量：4 个（干净的提交历史）
- 远程仓库：**尚未关联**（下一步操作）
- `.env` 文件：**被 Git 忽略，不会上传**

---

## 接下来你需要手动完成的步骤：

### 步骤 1：在 GitHub 创建仓库

1. 打开浏览器访问：https://github.com/new
2. 填写信息：
   - **Repository name**: `etf-selector-web`
   - **Description**: ETF智选专家 - 基于IMA知识库的Streamlit应用
   - **Visibility**: ⭐ **Public**（Streamlit Community Cloud 要求 Public）
   - ❌ **不要勾选** "Add a README file"
   - ❌ **不要勾选** "Add .gitignore"（我们已经有更好的）
   - ❌ **不要勾选** "Choose a license"
3. 点击 **Create repository**

### 步骤 2：关联并推送到 GitHub

GitHub 创建成功后会显示类似下面的命令，请在 PowerShell 中执行：

```powershell
cd C:\Users\ZTY\.qclaw\workspace\etf-selector-web

# 关联远程仓库
git remote add origin https://github.com/skyz72432-max/etf-selector-web.git

# 重命名分支为 main（GitHub 默认）
git branch -M main

# 推送到 GitHub
git push -u origin main
```

### 步骤 3：验证 GitHub 仓库安全

推送完成后，**务必检查**：

1. 打开：https://github.com/skyz72432-max/etf-selector-web
2. 点击 `data_layer.py` 文件查看内容
3. ✅ 确认**没有**出现任何密钥值（应该只有 `os.environ.get("IMA_API_KEY")`）
4. 点击 **Commits** 标签
5. ✅ 确认只有 4 个 commit，且都**不包含**密钥

### 步骤 4：Streamlit Community Cloud 部署

1. 打开：https://share.streamlit.io/
2. 点击 **New app**
3. 选择：
   - **Repository**: `skyz72432-max/etf-selector-web`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. 点击 **Deploy**

### 步骤 5：在 Streamlit Cloud 设置 Secrets

部署后，进入应用管理页面：

1. 点击左侧 **Settings** → **Secrets**
2. 添加以下三个环境变量：

   | Key | Value |
   |-----|-------|
   | `IMA_API_KEY` | `T/n8ion0drhG+MPB3WceJeb+ZEn1tVUf8rvDcCH14uMbrHckj8X3F1L6TcEYEPVRvkKYBigoMQ==` |
   | `IMA_CLIENT_ID` | `ab0cffc55c7a5d3387bd65a8b6fcbdea` |
   | `IMA_KB_ID` | `UTszrZSpiMrnwFqpoqbDUK4FQtj-ViA5VdslKHeIp8s=` |

3. 点击 **Save**
4. 点击 **Reboot** 重启应用

---

## 安全验证清单

| 检查项 | 状态 |
|--------|------|
| `data_layer.py` 中没有硬编码密钥 | ✅ 已完成 |
| 项目根目录有 `.env` 文件（本地使用） | ✅ 已完成 |
| `.env` 已添加到 `.gitignore` | ✅ 已完成 |
| `.gitignore` 已提交到 Git | ✅ 已完成 |
| GitHub 仓库中看不到 `.env` 文件 | ⬜ 待验证 |
| GitHub 仓库中 `data_layer.py` 没有密钥 | ⬜ 待验证 |
| Streamlit Cloud 已设置 Secrets | ⬜ 待完成 |
| 网站上线后能正常加载数据 | ⬜ 待验证 |

---

## 本地开发说明

`.env` 文件中的密钥仅供本地开发使用。当你运行 `streamlit run app.py` 时，`python-dotenv` 会自动加载这些环境变量，`data_layer.py` 就能正常读取。

**注意**：`.env` 文件永远不会被上传到 GitHub，所以是安全的。

---

## 需要帮助？

如果在任何步骤遇到问题，请告诉我：
1. 你当前执行到哪一步
2. 遇到了什么错误信息
3. 或者需要我帮你执行某个命令
