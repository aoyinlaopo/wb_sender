# 微博自动发博工具（Cookie 模拟登录，无需开发者）
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests


class WeiboPoster:
    """通过 Cookie 模拟登录微博，支持发送带图片的微博"""

    BASE_UPLOAD_URL = (
        "http://picupload.service.weibo.com/interface/pic_upload.php"
        "?mime=image%2Fjpeg&data=base64&url=0&markpos=1&logo=&nick=0&marks=1&app=miniblog"
    )
    POST_URL = "https://weibo.com/ajax/statuses/update"

    def __init__(self, cookie: str):
        self.cookie = cookie
        self.session = requests.Session()

        # 从 Cookie 中提取 XSRF-TOKEN（微博 Web API 校验必需）
        xsrf_token = ""
        for part in cookie.split("; "):
            if part.startswith("XSRF-TOKEN="):
                xsrf_token = part.split("=", 1)[1]
                break

        self.session.headers.update(
            {
                "Cookie": cookie,
                "Referer": "https://weibo.com/",
                "Origin": "https://weibo.com",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        if xsrf_token:
            self.session.headers["X-XSRF-TOKEN"] = xsrf_token

    # ── 图片上传 ───────────────────────────────────────────

    def upload_image(self, image_path: str) -> str:
        """上传图片到微博图床，返回 pid"""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")

        size = path.stat().st_size
        if size > 5 * 1024 * 1024:
            raise ValueError(f"图片过大 ({size} bytes)，建议 ≤ 5MB")

        pid = self._upload_via_base64(path)
        print(f"  📷 图片上传成功  pid={pid}")
        return pid

    def _upload_via_base64(self, path: Path) -> str:
        """Base64 方式上传（最稳定）"""
        import base64

        with open(path, "rb") as f:
            raw = f.read()
            b64_data = base64.b64encode(raw).decode()

        resp = self.session.post(self.BASE_UPLOAD_URL, data={"b64_data": b64_data})

        # 微博图床返回的是 HTML + JSON 混合体，需要提取纯 JSON 部分
        result = self._extract_json(resp.text)

        if result.get("code") != "A00006":
            raise RuntimeError(f"图片上传失败: {resp.text[:500]}")

        return result["data"]["pics"]["pic_1"]["pid"]

    def _upload_via_multipart(self, path: Path) -> str:
        """Multipart 方式上传（备用方案）"""
        timestamp = str(int(time.time() * 1000))
        url = (
            self.BASE_UPLOAD_URL
            + "&cb=http://weibo.com/aj/static/upimgback.html?_wv=5"
            + f"&callback=STK_ijax_{timestamp}"
        )

        with open(path, "rb") as f:
            files = {"pic1": (path.name, f, self._guess_mime(path))}
            resp = self.session.post(url, files=files)

        # 响应是 JSONP/HTML 混合格式
        result = self._extract_json(resp.text)
        if result.get("code") != "A00006":
            raise RuntimeError(f"图片上传失败: {result}")

        return result["data"]["pics"]["pic_1"]["pid"]

    @staticmethod
    def _extract_json(text: str) -> Dict:
        """从 HTML+JSON 混合响应中提取 JSON"""
        # 先尝试直接解析
        text_stripped = text.strip()
        if text_stripped.startswith("{"):
            try:
                return json.loads(text_stripped)
            except json.JSONDecodeError:
                pass
        # 用正则提取 JSON 对象
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise RuntimeError(f"无法从响应中提取 JSON: {text[:300]}")
        return json.loads(match.group())

    @staticmethod
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        return mime_map.get(ext, "image/jpeg")

    # ── 发微博 ─────────────────────────────────────────────

    def post_text(self, content: str) -> Dict:
        """发送纯文字微博"""
        return self._do_post(content)

    def post_with_image(self, content: str, image_path: str) -> Dict:
        """发送带图片的微博"""
        pid = self.upload_image(image_path)
        mime = self._guess_mime(Path(image_path))
        pic_id = json.dumps([{"type": mime, "pid": pid}])
        return self._do_post(content, pic_id=pic_id)

    def post_with_images(self, content: str, image_paths: List[str]) -> Dict:
        """发送带多张图片的微博"""
        pics = []
        for img_path in image_paths:
            pid = self.upload_image(img_path)
            mime = self._guess_mime(Path(img_path))
            pics.append({"type": mime, "pid": pid})
        pic_id = json.dumps(pics)
        return self._do_post(content, pic_id=pic_id)

    def _do_post(self, content: str, pic_id: Optional[str] = None) -> Dict:
        """核心发博逻辑 — 使用 /ajax/statuses/update 接口"""
        data = {
            "content": content,  # 注意：字段名是 content 不是 text
            "visible": "0",  # 0 = 公开
        }
        if pic_id:
            data["pic_id"] = pic_id

        resp = self.session.post(self.POST_URL, data=data)

        try:
            result = resp.json()
        except json.JSONDecodeError:
            raise RuntimeError(f"发博响应解析失败: {resp.text[:300]}")

        # /ajax/statuses/update 成功时返回 data 字段，失败时返回 code
        if "data" in result and "id" in result.get("data", {}):
            post_id = result["data"]["id"]
            print(f"  ✅ 发送成功: {content[:40]}... (id={post_id})")
        elif result.get("code") == "100000":
            print(f"  ✅ 发送成功: {content[:40]}...")
        elif result.get("code") == "100001":
            raise PermissionError(f"Cookie 已过期，请重新获取: {result}")
        else:
            raise RuntimeError(f"发送失败: {result}")

        return result

    # ── 工具方法 ───────────────────────────────────────────

    @staticmethod
    def pid_to_url(pid: str, size: str = "large") -> str:
        """将 pid 转为可访问的图片 URL"""
        return f"https://ws4.sinaimg.cn/{size}/{pid}"

    def check_login(self) -> bool:
        """检查 Cookie 是否仍有效"""
        resp = self.session.get("https://weibo.com/")
        return "我的主页" in resp.text or "WB_feed" in resp.text


# ── 便捷函数（供定时任务直接调用）─────────────────────────


def load_cookie_from_env() -> str:
    """从环境变量 WEIBO_COOKIE 加载 Cookie"""
    cookie = os.getenv("WEIBO_COOKIE")
    if not cookie:
        raise RuntimeError(
            "未设置 WEIBO_COOKIE 环境变量。\n"
            "请在 .env 文件中设置，或 export WEIBO_COOKIE='你的Cookie'"
        )
    return cookie


def post_text(content: str) -> Dict:
    """快捷：发纯文字微博"""
    poster = WeiboPoster(load_cookie_from_env())
    return poster.post_text(content)


def post_image(content: str, image_path: str) -> Dict:
    """快捷：发带图微博"""
    poster = WeiboPoster(load_cookie_from_env())
    return poster.post_with_image(content, image_path)
