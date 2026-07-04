# 微博自动发博工具 — 零基础搭建教程

无需编程知识，不用注册开发者，半小时内搞定定时发微博。

---

## 第一步：安装 Python

1. 打开 https://www.python.org/downloads/
2. 点击黄色按钮下载最新版（看到 `Download Python 3.x.x` 就点）
3. 运行下载的安装包
4. **⚠️ 重要**：第一屏底部勾选 **「Add Python to PATH」**（一定要勾！）
5. 点 `Install Now`，等待完成

验证是否装好：按 `Win+R`，输入 `cmd` 回车，在黑窗口里输入：

```
python --version
```

如果显示 `Python 3.x.x` 就说明装好了。

---

## 第二步：获取项目文件

### 方式 A：下载 ZIP（推荐，无需 git）

1. 打开 https://github.com/aoyinlaopo/wb_sender
2. 点绿色 `Code` 按钮 → `Download ZIP`
3. 解压到你想要的位置，比如 `D:\wb_sender\`

### 方式 B：用 git 克隆

```bash
git clone https://github.com/aoyinlaopo/wb_sender.git
```

---

## 第三步：获取微博 Cookie

这个是"钥匙"，让脚本能代你发微博。

1. 用 **Chrome 浏览器** 打开 https://weibo.com 并登录
2. 按 `F12` 打开开发者工具
3. 顶部点 `Application`（应用程序）标签（如果没看到，点 `>>` 展开找）
4. 左侧找到 `Cookies` → 点 `https://weibo.com`
5. 在右侧表格中，找到并**全选所有行**，复制（Ctrl+C）
6. 也可以只复制 `SUB`、`SUBP`、`XSRF-TOKEN`、`SCF`、`WBPSESS` 这几个关键字段

> Cookie 格式像这样：`SUB=_2A25...; SUBP=0033W...; XSRF-TOKEN=...`

---

## 第四步：配置 Cookie

在项目目录下，把 `.env.example` **复制一份**，重命名为 `.env`。

用**记事本**打开 `.env`，把等号后面的内容替换成你的 Cookie：

```
WEIBO_COOKIE=你复制的Cookie字符串
```

保存关闭。

---

## 第五步：安装依赖

按 `Win+R`，输入 `cmd` 回车。在黑窗口里：

```bash
cd /d D:\wb_sender
pip install requests python-dotenv
```

> 路径换成你实际解压的位置。看到 `Successfully installed` 就是装好了。

---

## 第六步：准备文案和图片

在项目目录下有两个文件夹：

```
wb_sender/
├── wenan/        ← 文案放这里
│   ├── 文案1.txt
│   ├── 文案2.txt
│   └── 文案3.txt
├── images/       ← 图片放这里
│   ├── 文案1.jpg
│   ├── 文案2.jpg
│   └── 文案3.jpg
```

**规则**：
- 文案文件和图片文件**编号对应**：`文案1.txt` 配 `文案1.jpg`
- 图片支持 `.jpg` `.png` `.gif` `.webp`
- 想加更多就继续编号：`文案4.txt` + `文案4.jpg`，自动识别

---

## 第七步：测试发送

在 cmd 窗口中：

```bash
# 发一条带图微博（手动指定）
python scheduler.py --once --text "测试文案" --image ./images/文案1.jpg

# 检查 Cookie 是否有效
python scheduler.py --check

# 轮询模式：自动发下一条
python scheduler.py --once --rotate
```

---

## 第八步：设置定时任务

### 每天定时发送

以管理员身份打开 cmd（`Win` 键 → 输入 `cmd` → 右键 → **以管理员身份运行**）：

```bash
# 每天 8:00
schtasks /create /tn "微博8点" /tr "D:\wb_sender\run.bat" /sc daily /st 08:00 /f

# 每天 12:00
schtasks /create /tn "微博12点" /tr "D:\wb_sender\run.bat" /sc daily /st 12:00 /f

# 每天 18:00
schtasks /create /tn "微博18点" /tr "D:\wb_sender\run.bat" /sc daily /st 18:00 /f

# 每天 22:00
schtasks /create /tn "微博22点" /tr "D:\wb_sender\run.bat" /sc daily /st 22:00 /f
```

> 路径 `D:\wb_sender\run.bat` 换成你实际的项目路径。时间可以随便改。

### 其他频率示例

```bash
# 每 2 小时一次
schtasks /create /tn "微博定时" /tr "D:\wb_sender\run.bat" /sc hourly /mo 2 /f

# 每 30 分钟一次
schtasks /create /tn "微博定时" /tr "D:\wb_sender\run.bat" /sc minute /mo 30 /f
```

### 管理定时任务

- 查看所有任务：`Win+R` → 输入 `taskschd.msc` → 回车
- 停用任务：找到任务 → 右键 → **禁用**
- 删除任务：以管理员身份运行 cmd：

```bash
# 删除单个
schtasks /delete /tn "微博8点" /f

# 删除全部
schtasks /delete /tn "微博8点" /f
schtasks /delete /tn "微博12点" /f
schtasks /delete /tn "微博18点" /f
schtasks /delete /tn "微博22点" /f
```

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `python 不是内部命令` | 没勾选 Add Python to PATH | 重装 Python，勾选那个选项 |
| `ModuleNotFoundError` | 没装依赖 | 执行 `pip install requests python-dotenv` |
| `Cookie 已过期` | SUB Cookie 1-3 天失效 | 重新从浏览器复制 Cookie 更新 `.env` |
| 发了但没图片 | 接口问题 | 确认文案和图片编号对应 |
| 定时任务没触发 | 电脑休眠/关机了 | 定时任务需要电脑开着 |

---

## 备注

- Cookie 一般 **1-3 天** 过期，建议每两天手动更新一次
- 微博每小时最多发 **45 条**，别设太频繁
- 电脑需要保持开机才能触发定时任务
