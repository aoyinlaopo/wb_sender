# 微博自动发博工具

无需注册微博开发者，通过 Cookie 模拟登录实现**定时发送带图片的微博**。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Cookie

1. 用浏览器登录 [weibo.com](https://weibo.com)
2. 按 `F12` → `Application`（应用程序）→ `Cookies` → `weibo.com`
3. 找到 `SUB` 这个 Cookie，复制它的值
4. 把整个 Cookie 字符串复制出来（至少包含 `SUB=xxx; SUBP=xxx;`）

> ⚠️ Cookie 有效期一般 **1-3 天**，过期需要重新获取。

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env，把 WEIBO_COOKIE= 后面替换成你复制的 Cookie
```

### 4. 运行

```bash
# 发纯文字微博
python scheduler.py --once --text "Hello 微博！这是一条测试 👋"

# 发带图微博
python scheduler.py --once --text "今天的晚霞好美 🌅" --image ./images/sunset.jpg

# 检查 Cookie 是否有效
python scheduler.py --check

# 从配置文件随机发（推荐用于定时任务）
cp posts.example.json posts.json
# 编辑 posts.json 填入你想发的内容
python scheduler.py --once --from-json posts.json
```

## 定时发送

### 方式 A：GitHub Actions（推荐，免费免运维）

1. 把代码推到 GitHub 仓库
2. 在仓库 `Settings` → `Secrets and variables` → `Actions` 中添加 `WEIBO_COOKIE`
3. 编辑 `.github/workflows/post-weibo.yml` 修改 cron 时间
4. GitHub 会按照 cron 时间自动运行

**默认**：每天 UTC 1:00（北京时间 9:00）自动发一条。

### 方式 B：Windows 任务计划程序

1. 打开"任务计划程序"（`taskschd.msc`）
2. 创建基本任务 → 触发器设为"每天"
3. 操作 → 启动程序：

```
程序: C:\Python311\python.exe
参数: D:\Workspace\llm\daily\scheduler.py --once --from-json D:\Workspace\llm\daily\posts.json
起始于: D:\Workspace\llm\daily
```

### 方式 C：Linux/Mac Cron

```bash
# 每天早 8 点发
0 8 * * * cd /path/to/project && python scheduler.py --once --from-json posts.json >> /tmp/weibo.log 2>&1
```

## posts.json 配置说明

```json
{
  "posts": [
    {
      "text": "微博内容",
      "image": "图片路径 或 图片文件夹/ 或 null"
    }
  ]
}
```

- `image` 是**文件路径**：固定发这张图
- `image` 是**文件夹路径**（以 `/` 结尾）：从文件夹中**随机选一张图**
- `image` 是 `null`：纯文字微博

支持 jpg、png、gif、webp 格式，单张 ≤ 5MB。

## 项目结构

```
├── weibo_poster.py   # 核心模块：图片上传 + 发微博
├── scheduler.py      # 调度器：CLI 入口 + 定时任务
├── posts.json        # 待发内容配置（需自己创建）
├── .env              # Cookie 配置（需自己创建）
├── images/           # 图片文件夹
└── .github/workflows/post-weibo.yml  # GitHub Actions 配置
```
