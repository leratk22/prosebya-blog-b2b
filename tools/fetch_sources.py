"""Собирает названия материалов по внешним ссылкам статей → content/sources.json.
В «Источниках» ссылкой становится название материала, а не слова из текста, в которые зашита ссылка.
Если страница не отдала заголовок, остаётся название издателя (SOURCE_NAMES в build.py).

Запуск: python3 tools/fetch_sources.py   (скачивает только новые ссылки)
"""
import json
import re
import subprocess
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

OUT = build.ROOT / "content" / "sources.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

# хвосты вида « | Gallup», « - SHRM»: издатель и так стоит рядом
SUFFIX = re.compile(r"\s+(?:\||–|—|::|-)\s+[^|–—:]{2,40}$")
PREFIX = re.compile(r"^[A-ZА-Я][\w.&]{1,15}\s+\|\s+")          # «CIPD | …»
JUNK = re.compile(r"(?:just a moment|attention required|access denied|\b40[34]\b|page not found|not found|"
                  r"verifying you are human|security check|redirecting|проверка браузера|captcha|"
                  r"client challenge|who we are|community$|archives|^error)", re.I)


def urls():
    posts = build.load_posts()
    slugs = {p["slug"] for p in posts}
    seen = []
    for p in posts:
        blocks = build.parse((build.RAW / f"{p['slug']}.html").read_text(), slugs)
        for href, _, _ in build.sources_from(blocks):
            if href not in seen:
                seen.append(href)
    return seen


def title_of(url):
    r = subprocess.run(["curl", "-sL", "--max-time", "20", "-A", UA, "-H", "Accept-Language: ru,en;q=0.8", url],
                       capture_output=True)
    html = r.stdout[:400_000].decode("utf-8", "ignore")
    for pattern in (r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
                    r'<meta[^>]+content="([^"]+)"[^>]+property="og:title"',
                    r'<meta[^>]+name="citation_title"[^>]+content="([^"]+)"',
                    r"<title[^>]*>(.*?)</title>"):
        m = re.search(pattern, html, re.S | re.I)
        if m:
            t = re.sub(r"\s+", " ", unescape(m.group(1))).strip()
            if len(t) > 12 and not JUNK.match(t):
                return t
    return ""


def clean(title, host):
    """Заголовок страницы → название материала; пустая строка, если заголовок бесполезен."""
    name = build.SOURCE_NAMES.get(host, "")
    t = title
    if not t or JUNK.search(t) or t.strip().lower() in (host, "www." + host):
        return ""
    for _ in range(2):  # срезаем « | Издатель», « :: РБК» и подобное в конце
        m = SUFFIX.search(t)
        if m and len(t) - len(m.group(0)) > 20:
            t = t[: m.start()]
    if " | " in t and len(t.split(" | ")[0]) > 20:  # «Название | длинный хвост сайта»
        t = t.split(" | ")[0]
    t = PREFIX.sub("", t)
    if name and t.lower().startswith(name.lower() + ":"):
        t = t[len(name) + 1:].strip()
    return t[:140].rstrip(" .,:;")


def main():
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    for url in urls():
        if url not in data:
            data[url] = {"raw": title_of(url)}
    for url, v in data.items():  # чистим заново при каждом запуске: правила могли поменяться
        v["title"] = clean(v.get("raw", ""), urlparse(url).netloc.replace("www.", ""))
        print(("OK  " if v["title"] else "--  ") + urlparse(url).netloc, "|", v["title"][:100])
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    got = sum(1 for v in data.values() if v["title"])
    print(f"\nНазвания найдены для {got} из {len(data)} ссылок → {OUT.relative_to(build.ROOT)}")


if __name__ == "__main__":
    main()
