"""
定时发微博调度器 — 支持多种运行模式

用法:
  # 一次性发送（适合 cron / GitHub Actions）
  python scheduler.py --once --text "早安！今天也是元气满满的一天" --images ./photo1.jpg ./photo2.jpg

  # 轮询模式（推荐！自动读取 wenan/ + images/ 目录，按顺序轮发）
  python scheduler.py --once --rotate

  # 轮询 + 持续运行模式
  python scheduler.py --daemon --rotate --cron "0 9,12,18,22 * * *"

  # 预配置模式（从 posts.json 随机选）
  python scheduler.py --once --from-json posts.json
"""

import argparse
import json
import os
import re
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from weibo_poster import WeiboPoster, load_cookie_from_env

load_dotenv()

# ── 轮询模式 ─────────────────────────────────────────────────

ROTATE_STATE_FILE = ".rotate_state.json"
DEFAULT_WENAN_DIR = "wenan"
DEFAULT_IMAGES_DIR = "images"


def discover_posts(wenan_dir: str, images_dir: str) -> List[Tuple[str, str]]:
    """
    扫描文案和图片目录，按编号配对。
    支持两种图片组织方式：
      - 多图：images/文案N/ 子文件夹，放 1-9 张图片
      - 单图：images/文案N.jpg（兼容旧方式）
    返回 [(文案内容, [图片路径列表]), ...]。
    """
    wenan_path = Path(wenan_dir)
    images_path = Path(images_dir)

    if not wenan_path.is_dir():
        raise FileNotFoundError(f"文案目录不存在: {wenan_dir}")
    if not images_path.is_dir():
        raise FileNotFoundError(f"图片目录不存在: {images_dir}")

    IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    pattern = re.compile(r"^文案(\d+)\.txt$")
    entries: List[Tuple[int, str, List[str]]] = []  # [(编号, 文本路径, [图片路径列表])]

    for txt_file in sorted(wenan_path.iterdir()):
        match = pattern.match(txt_file.name)
        if not match:
            continue
        num = int(match.group(1))

        # 优先检查子文件夹（多图模式）
        sub_dir = images_path / f"文案{num}"
        if sub_dir.is_dir():
            imgs = sorted([
                str(p) for p in sub_dir.iterdir()
                if p.suffix.lower() in IMG_EXTS
            ])[:9]  # 微博最多 9 张
            if imgs:
                entries.append((num, str(txt_file), imgs))
                print(f"  📋 [{num}] {txt_file.name} ↔ {sub_dir.name}/ ({len(imgs)}张图)")
                continue
            else:
                print(f"  ⚠️  文案{num}/ 文件夹为空，跳过")

        # 回退：单文件匹配（旧方式）
        img_file = None
        for ext in IMG_EXTS:
            candidate = images_path / f"文案{num}{ext}"
            if candidate.exists():
                img_file = candidate
                break

        if img_file:
            entries.append((num, str(txt_file), [str(img_file)]))
            print(f"  📋 [{num}] {txt_file.name} ↔ {img_file.name}")
        else:
            print(f"  ⚠️  文案{num}.txt 没有找到对应图片，跳过")

    if not entries:
        raise RuntimeError(
            "没有找到可配对的文案和图片。\n"
            "  单图：wenan/文案N.txt ↔ images/文案N.jpg\n"
            "  多图：wenan/文案N.txt ↔ images/文案N/*.jpg"
        )

    # 按编号排序
    entries.sort(key=lambda x: x[0])

    # 读取文案内容
    result: List[Tuple[str, List[str]]] = []
    for num, txt_path, img_paths in entries:
        text = Path(txt_path).read_text(encoding="utf-8").strip()
        result.append((text, img_paths))

    return result


def load_rotate_state() -> Dict:
    """读取轮询状态"""
    if Path(ROTATE_STATE_FILE).exists():
        return json.loads(Path(ROTATE_STATE_FILE).read_text(encoding="utf-8"))
    return {"index": -1, "total": 0}


def save_rotate_state(state: Dict):
    """保存轮询状态"""
    Path(ROTATE_STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_rotate(
    wenan_dir: str = DEFAULT_WENAN_DIR,
    images_dir: str = DEFAULT_IMAGES_DIR,
):
    """
    轮询发送：自动扫描目录，按顺序发下一条。
    每次调用发一条，发完一轮从头开始。
    """
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 🔄 轮询模式启动...")

    posts = discover_posts(wenan_dir, images_dir)
    print(f"  共发现 {len(posts)} 组文案+图片")

    state = load_rotate_state()
    total = len(posts)

    # 如果总数变了（增删了文件），重置
    if state["total"] != total:
        state = {"index": -1, "total": total}

    # 下一条的索引
    next_index = (state["index"] + 1) % total
    text, images = posts[next_index]

    print(f"  📤 发送第 {next_index + 1}/{total} 条")
    send_once(text, images)

    # 保存状态
    state["index"] = next_index
    state["total"] = total
    save_rotate_state(state)
    print(f"  💾 状态已保存（下次将从第 {(next_index + 1) % total + 1} 条开始）")


# ── 一次性发送 ─────────────────────────────────────────────


def send_once(text: str, images: Optional[List[str]] = None):
    """发送一条微博（支持多图，最多9张）"""
    cookie = load_cookie_from_env()
    poster = WeiboPoster(cookie)
    poster.warmup()  # 预热会话，降低风控概率

    if images:
        if len(images) == 1:
            poster.post_with_image(text, images[0])
        else:
            poster.post_with_images(text, images)
    else:
        poster.post_text(text)

    print("🎉 完成!")


# ── 从配置文件发送 ─────────────────────────────────────────


def send_from_json(json_path: str):
    """从 JSON 文件随机选取内容发送"""
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 📂 从 {json_path} 加载内容...")

    with open(json_path, encoding="utf-8") as f:
        config = json.load(f)

    posts = config.get("posts", [])
    if not posts:
        print("❌ posts.json 中没有待发内容")
        sys.exit(1)

    post = random.choice(posts)
    text = post["text"]

    images = None
    img_config = post.get("image") or post.get("images")
    if img_config:
        if isinstance(img_config, list):
            # 图片列表：["a.jpg", "b.jpg"]
            images = img_config
        elif isinstance(img_config, str):
            img_path = Path(img_config)
            if img_path.is_dir():
                # 文件夹：随机选一张
                exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
                all_imgs = [str(p) for p in img_path.iterdir() if p.suffix.lower() in exts]
                if all_imgs:
                    images = all_imgs[:9]
            elif img_path.is_file():
                images = [str(img_path)]

    send_once(text, images)


# ── 持续运行模式（APScheduler）──────────────────────────────


def run_daemon_rotate(cron_expr: str, wenan_dir: str, images_dir: str):
    """后台持续运行，按 cron 轮询发送"""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()

    def job():
        try:
            send_rotate(wenan_dir, images_dir)
        except Exception as e:
            print(f"❌ 发送失败: {e}")

    scheduler.add_job(job, "cron", **parse_cron(cron_expr))

    print(f"⏰ 轮询调度器已启动，cron: {cron_expr}")
    print(f"📂 文案目录: {wenan_dir}")
    print(f"🖼️  图片目录: {images_dir}")
    print("按 Ctrl+C 停止")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n👋 调度器已停止")


def parse_cron(expr: str) -> Dict[str, str]:
    """解析 cron 表达式: minute hour day month day_of_week"""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"cron 表达式格式错误（需要 5 个字段）: {expr}")

    keys = ["minute", "hour", "day", "month", "day_of_week"]
    parsed = {}
    for key, val in zip(keys, parts):
        if val != "*":
            parsed[key] = val
    return parsed


# ── CLI 入口 ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="微博定时发送工具")
    parser.add_argument(
        "--once", action="store_true", help="发送一次后退出（适合 cron / GitHub Actions）"
    )
    parser.add_argument("--text", type=str, help="微博文本内容")
    parser.add_argument("--images", type=str, nargs="+", help="图片路径，支持多张（空格分隔）")
    parser.add_argument(
        "--from-json", type=str, metavar="FILE", help="从 JSON 配置文件随机选取内容发送"
    )
    parser.add_argument(
        "--rotate", action="store_true",
        help="轮询模式：自动扫描 wenan/ 和 images/ 目录，按顺序轮发"
    )
    parser.add_argument(
        "--wenan-dir", type=str, default=DEFAULT_WENAN_DIR, help=f"文案目录（默认: {DEFAULT_WENAN_DIR}/）"
    )
    parser.add_argument(
        "--images-dir", type=str, default=DEFAULT_IMAGES_DIR, help=f"图片目录（默认: {DEFAULT_IMAGES_DIR}/）"
    )
    parser.add_argument(
        "--daemon", action="store_true", help="持续运行模式（需要 APScheduler，配合 --rotate 或 --from-json）"
    )
    parser.add_argument(
        "--cron", type=str, default="0 9 * * *", help='cron 表达式，默认 "0 9 * * *" (每天9点)'
    )
    parser.add_argument(
        "--check", action="store_true", help="仅检查 Cookie 是否有效"
    )

    args = parser.parse_args()

    if args.check:
        cookie = load_cookie_from_env()
        poster = WeiboPoster(cookie)
        valid = poster.check_login()
        if valid:
            print("✅ Cookie 有效，登录状态正常")
        else:
            print("❌ Cookie 已失效，请重新获取")
        return

    if args.daemon:
        if args.rotate:
            run_daemon_rotate(args.cron, args.wenan_dir, args.images_dir)
        elif args.from_json:
            print("❌ daemon + from-json 暂不支持，请用 --rotate 代替")
            sys.exit(1)
        else:
            print("❌ daemon 模式需要 --rotate 或 --from-json 参数")
            sys.exit(1)
    elif args.rotate:
        send_rotate(args.wenan_dir, args.images_dir)
    elif args.from_json:
        send_from_json(args.from_json)
    elif args.once:
        if not args.text:
            print("❌ --once 模式需要 --text 参数")
            sys.exit(1)
        send_once(args.text, args.images)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
