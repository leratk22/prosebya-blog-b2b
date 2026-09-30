"""Забирает тексты статей с prosebya.ru/blog-b2b (Tilda) в content/raw/<slug>.html.
Запуск: python3 tools/fetch_articles.py"""
import json, re, subprocess, sys, time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "raw"
META = ROOT / "content" / "meta"
VOID = {"br", "img", "hr", "meta", "link", "input", "source", "wbr"}


def slugs():
    js = (ROOT / "assets" / "posts.js").read_text()
    return re.findall(r'slug: "([^"]+)"', js.split("window.BLOG_POSTS")[1])


class Grab(HTMLParser):
    """Возвращает внутренний HTML первого элемента с классом js-feed-post-text."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.buf = []
        self.done = False

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if self.depth:
            self.buf.append(self.get_starttag_text())
            if tag not in VOID:
                self.depth += 1
        elif "js-feed-post-text" in (dict(attrs).get("class") or ""):
            self.depth = 1

    def handle_startendtag(self, tag, attrs):
        if self.depth and not self.done:
            self.buf.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not self.depth or self.done or tag in VOID:
            return
        self.depth -= 1
        if self.depth == 0:
            self.done = True
        else:
            self.buf.append(f"</{tag}>")

    def handle_data(self, data):
        if self.depth and not self.done:
            self.buf.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    for slug in slugs():
        url = f"https://prosebya.ru/blog-b2b/{slug}"
        if (OUT / f"{slug}.html").exists() and (META / f"{slug}.json").exists():
            continue
        html = ""
        for attempt in range(4):
            r = subprocess.run(["curl", "-sL", "-A", "Mozilla/5.0 (Macintosh)", "-w", "\n%{http_code}", url],
                               capture_output=True, text=True)
            html, _, code = r.stdout.rpartition("\n")
            if code == "200":
                break
            time.sleep(5 * (attempt + 1))
        else:
            print("FAIL", slug, code, file=sys.stderr)
            continue
        g = Grab()
        g.feed(html)
        body = "".join(g.buf).strip()
        if not body:
            print("EMPTY", slug, file=sys.stderr)
            continue
        (OUT / f"{slug}.html").write_text(body)
        # SEO-поля страницы: пригодятся при переносе (Yoast / Rank Math)
        def meta(pattern):
            m = re.search(pattern, html, re.S)
            return unescape(m.group(1).strip()) if m else ""
        (META / f"{slug}.json").write_text(json.dumps({
            "seo_title": meta(r"<title>(.*?)</title>"),
            "seo_description": meta(r'<meta name="description" content="([^"]*)"'),
            "og_image": meta(r'<meta property="og:image" content="([^"]*)"'),
            "url": url,
        }, ensure_ascii=False, indent=2))
        print(f"{slug}: {len(body)}")
        time.sleep(2)


if __name__ == "__main__":
    main()
