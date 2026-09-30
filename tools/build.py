"""Собирает страницы статей blog/<slug>.html из текстов Tilda (content/raw) по шаблону нового дизайна.

Что делает с текстом:
- абзацы из <br><br> → <p>; строки с «•», «—», «-» → маркированный список; «1.», «2)» → нумерованный;
- таблицы Tilda → блок таблицы с копированием и CSV (у исходных таблиц нет строки заголовка — первый столбец считаем заголовком строки);
- первый абзац, дословно повторяющий анонс, убирается (анонс уже стоит лидом);
- последний раздел (реклама Просебя) → CTA-блок;
- внешние ссылки собираются в «Источники», ссылки на другие статьи блога ведут на локальные страницы;
- время чтения считается по объёму текста (180 слов в минуту) и записывается в assets/posts.js.

Запуск: python3 tools/build.py
"""
import hashlib
import json
import math
import re
from html import escape, unescape
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "content" / "raw"
META = ROOT / "content" / "meta"
OUT = ROOT / "blog"

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа",
          "сентября", "октября", "ноября", "декабря"]
TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                     "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))

ICON_DATE = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="1.75" y="2.75" width="10.5" height="9.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M1.75 5.75H12.25M4.75 1.5V3.5M9.25 1.5V3.5" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>'
ICON_TIME = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M7 4.2V7L8.8 8.2" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_ARROW = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_CHEVRON = '<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ICON_COPY = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="4.25" y="4.25" width="8" height="8" rx="1.75" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M9.75 2.25H3.75C2.92 2.25 2.25 2.92 2.25 3.75V9.75" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>'
ICON_DOWNLOAD = '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M7 2V9M7 9L4.25 6.25M7 9L9.75 6.25M2.5 11.75H11.5" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>'


# ---------- данные ----------

def load_posts():
    js = (ROOT / "assets" / "posts.js").read_text()
    body = js.split("window.BLOG_POSTS")[1]
    posts = []
    for m in re.finditer(r"\{ slug: .*?\},?\n", body, re.S):
        chunk = m.group(0)
        get = lambda k: (re.search(rf'{k}: "((?:[^"\\]|\\.)*)"', chunk) or [None, ""])[1]
        posts.append({
            "slug": get("slug"), "cat": get("cat"), "date": get("date"), "img": get("img"),
            "title": get("title"), "excerpt": get("excerpt"),
            "framed": "framed: true" in chunk,
        })
    return posts


def categories():
    js = (ROOT / "assets" / "posts.js").read_text()
    return dict((n, s) for s, n in re.findall(r'\{ slug: "([^"]+)", name: "([^"]+)" \}', js))


# ---------- утилиты ----------

def slugify(text):
    text = unescape(re.sub(r"<[^>]+>", "", text)).lower()
    out = "".join(TRANSLIT.get(ch, ch) for ch in text)
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:60].rstrip("-") or "razdel"


def plain(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


CARD_SIZES = "(max-width: 767px) calc(100vw - 32px), (max-width: 1279px) calc(50vw - 60px), 416px"


def render_card(post, base, eager=False):
    """Карточка статьи. Разметка совпадает с renderCard в assets/blog.js."""
    c = f"{base}assets/covers/{post['slug']}"
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (
        '\n      <li class="card">'
        f'\n        <div class="card__cover"><img src="{c}-416.webp" srcset="{c}-416.webp 416w, {c}-832.webp 832w"'
        f' sizes="{CARD_SIZES}" width="416" height="312" alt="" {loading} decoding="async"'
        ' onload="this.classList.add(\'is-loaded\')"></div>'
        f'\n        <div class="card__category">{escape(post["cat"])}</div>'
        f'\n        <h3 class="card__title"><a class="card__link" href="{base}blog/{post["slug"]}.html">{escape(post["title"])}</a></h3>'
        f'\n        <p class="card__excerpt">{escape(post["excerpt"])}</p>'
        '\n        <div class="card__meta">'
        f'\n          <span>{ICON_DATE}<time datetime="{post["date"]}">{fmt_date(post["date"])}</time></span>'
        f'\n          <span>{ICON_TIME}<span>{post["read"]} мин</span></span>'
        '\n        </div>'
        '\n      </li>'
    )


# ---------- разбор текста Tilda ----------

BULLET = re.compile(r"^(?:•|—|–|-)\s+")
NUMBER = re.compile(r"^\d{1,2}[.)]\s+")
# маркер может стоять внутри выделения: <strong>• Текст</strong>
LEAD_TAGS = r"^((?:\s*<(?:strong|em)>)*)\s*"
BULLET_HTML = re.compile(LEAD_TAGS + r"(?:•|—|–|-)\s+")
NUMBER_HTML = re.compile(LEAD_TAGS + r"\d{1,2}[.)]\s+")


def clean_inline(html, slugs):
    """Оставляет только a/strong/em/br, чинит ссылки на статьи блога."""
    html = re.sub(r"<(/?)b>", r"<\1strong>", html)
    html = re.sub(r"<(/?)i>", r"<\1em>", html)

    def link(m):
        href = unescape(m.group(1))
        p = urlparse(href)
        if p.netloc.endswith("prosebya.ru") and p.path.startswith("/blog-b2b/"):
            slug = p.path.rstrip("/").split("/")[-1]
            if slug in slugs:
                return f'<a href="{slug}.html">'
        return f'<a href="{escape(href)}">'

    html = re.sub(r'<a\s[^>]*href="([^"]*)"[^>]*>', link, html)
    html = re.sub(r"<(?!/?(?:a|strong|em|br)\b)[^>]+>", "", html)
    return html.replace("&nbsp;", " ").strip()


def text_blocks(div_html, slugs):
    """Текстовый блок Tilda → список блоков (p, ul, ol)."""
    blocks = []
    for chunk in re.split(r"(?:<br\s*/?>\s*){2,}", div_html):
        lines = [l.strip() for l in re.split(r"<br\s*/?>", chunk) if plain(l)]
        para = []
        for line in lines:
            text = plain(line)
            kind = "ul" if BULLET.match(text) else "ol" if NUMBER.match(text) else None
            if kind:
                if para:
                    blocks.append(("p", "<br>".join(para)))
                    para = []
                item = clean_inline(line, slugs)
                item = (BULLET_HTML if kind == "ul" else NUMBER_HTML).sub(r"\1", item, count=1)
                if blocks and blocks[-1][0] == kind:
                    blocks[-1][1].append(item)
                else:
                    blocks.append((kind, [item]))
            else:
                para.append(clean_inline(line, slugs))
        if para:
            blocks.append(("p", "<br>".join(para)))
    return blocks


def table_block(table_html, slugs):
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
        cells = [clean_inline(c, slugs) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if any(plain(c) for c in cells):
            rows.append(cells)
    return ("table", rows)


def parse(raw, slugs):
    """Сырой HTML статьи → список блоков по порядку."""
    token = re.compile(
        r'<h2[^>]*>(?P<h2>.*?)</h2>'
        r'|<h3[^>]*>(?P<h3>.*?)</h3>'
        r'|<div class="t-table__viewport">(?P<table>.*?</table>)'
        r'|<div class="t-redactor__text">(?P<text>.*?)</div>', re.S)
    blocks = []
    for m in token.finditer(raw):
        if m.group("h2") is not None:
            blocks.append(("h2", clean_inline(m.group("h2"), slugs)))
        elif m.group("h3") is not None:
            blocks.append(("h3", clean_inline(m.group("h3"), slugs)))
        elif m.group("table") is not None:
            blocks.append(table_block(m.group("table"), slugs))
        else:
            blocks.extend(text_blocks(m.group("text"), slugs))
    # склеиваем соседние списки одного вида (пункты, разделённые пустой строкой)
    merged = []
    for b in blocks:
        if merged and b[0] in ("ul", "ol") and merged[-1][0] == b[0]:
            merged[-1][1].extend(b[1])
        else:
            merged.append(b)
    return merged


# ---------- отрисовка ----------

def render_blocks(blocks, table_name, table_header=None):
    html, toc, used = [], [], set()
    for kind, val in blocks:
        if kind == "h2":
            hid = slugify(val)
            while hid in used:
                hid += "-2"
            used.add(hid)
            toc.append((hid, plain(val)))
            html.append(f'<h2 id="{hid}">{val}</h2>')
        elif kind == "h3":
            html.append(f"<h3>{val}</h3>")
        elif kind == "p":
            html.append(f"<p>{val}</p>")
        elif kind in ("ul", "ol"):
            items = "".join(f"<li>{i}</li>" for i in val)
            html.append(f"<{kind}>{items}</{kind}>")
        elif kind == "table":
            body = "".join(
                "<tr>" + f'<th scope="row">{r[0]}</th>' + "".join(f"<td>{c}</td>" for c in r[1:]) + "</tr>"
                for r in val)
            head = ""
            if table_header:  # на Tilda у таблиц нет шапки — берём из content/table-headers.json
                head = "<thead><tr>" + "".join(f'<th scope="col">{escape(h)}</th>' for h in table_header) + "</tr></thead>"
            html.append(f'''<div class="table-block" data-name="{table_name}">
          <div class="table-scroll" tabindex="0" role="region" aria-label="Таблица">
            <table>{head}<tbody>{body}</tbody></table>
          </div>
          <div class="table-actions">
            <button class="table-action" type="button" data-table-copy>{ICON_COPY}<span>Скопировать таблицу</span></button>
            <button class="table-action" type="button" data-table-csv>{ICON_DOWNLOAD}<span>Скачать CSV</span></button>
          </div>
        </div>''')
    return "\n        ".join(html), toc


SOURCE_NAMES = {
    "gallup.com": "Gallup", "press.rabota.ru": "Работа.ру", "rabota.ru": "Работа.ру",
    "sberanalytics.ru": "СберАналитика", "who.int": "ВОЗ", "deloitte.com": "Deloitte",
    "deloittedigital.com": "Deloitte Digital", "insur-info.ru": "Insur-info", "wciom.ru": "ВЦИОМ",
    "pmc.ncbi.nlm.nih.gov": "PubMed Central", "pubmed.ncbi.nlm.nih.gov": "PubMed",
    "prnewswire.com": "PR Newswire", "eapa.org.uk": "EAPA UK", "shrm.org": "SHRM",
    "workinstitute.com": "Work Institute", "info.workinstitute.com": "Work Institute",
    "doi.org": "Научная статья (DOI)", "stats.hh.ru": "hh.ru", "rgs.ru": "Росгосстрах",
    "tandfonline.com": "Taylor & Francis", "scribd.com": "Scribd", "developernation.net": "Developer Nation",
    "usehaystack.io": "Haystack", "getexperts.ru": "GetExperts", "cipd.org": "CIPD",
    "rework.withgoogle.com": "Google re:Work", "marketing.rbc.ru": "РБК", "ecopsy.ru": "ЭКОПСИ",
    "pubsonline.informs.org": "INFORMS", "microsoft.com": "Microsoft", "mckinsey.com.cn": "McKinsey",
    "mckinsey.com": "McKinsey", "bamboohr.com": "BambooHR", "journals.sagepub.com": "SAGE Journals",
}


def sources_from(blocks):
    """Внешние ссылки из текста → (href, название источника, фраза из текста)."""
    seen, out = set(), []
    for kind, val in blocks:
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            if isinstance(v, list):  # строки таблицы
                v = " ".join(v)
            for href, label in re.findall(r'<a href="([^"]+)">(.*?)</a>', v, re.S):
                href = unescape(href)
                host = urlparse(href).netloc.replace("www.", "")
                if not host or host.endswith("prosebya.ru") or href in seen:
                    continue
                seen.add(href)
                name = SOURCE_NAMES.get(host, host)
                context = plain(label).rstrip(".,:;")
                out.append((href, name, context))
    return out


def reading_minutes(blocks):
    words = 0
    for kind, val in blocks:
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            words += len(plain(" ".join(v) if isinstance(v, list) else v).split())
    return max(3, math.ceil(words / 180))


# Черновые описания категорий — заменить текстами редакции
CATEGORY_LEADS = {
    "tekuchest-i-vygoranie": "Почему люди уходят и выгорают, как это измерить и что компания может изменить до заявления об уходе.",
    "lgoty-i-motivaciya": "Какие льготы сотрудники ценят на деле, как считать их использование и где место психологической поддержке.",
    "vybor-eap": "Как выбрать программу поддержки сотрудников: форматы, цены, отличия от ДМС и вопросы провайдеру.",
    "byudzhet-i-roi": "Как посчитать эффект поддержки в деньгах и защитить бюджет перед руководством.",
    "vnedrenie": "Как запустить программу поддержки и добиться, чтобы ей действительно пользовались.",
    "metriki-i-upravlenie": "Как измерять состояние команды на обезличенных данных и управлять им, а не ощущениями.",
}
BLOG_LEAD = "Как бизнес работает с психологическим состоянием команды. Для HR-директоров, HR BP и руководителей."
PER_PAGE = 12


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def build_listings(posts, cats):
    """index.html и category/<slug>.html: шапка, чипы и первые 12 карточек сразу в HTML."""
    shell = (ROOT / "tools" / "listing-shell.html").read_text()
    shell = shell.split("-->\n", 1)[1]  # служебный комментарий шаблона
    pages = [(None, ROOT / "index.html", "")] + [
        (slug, ROOT / "category" / f"{slug}.html", "../") for slug in cats.values()]
    (ROOT / "category").mkdir(exist_ok=True)
    counts = {name: sum(p["cat"] == name for p in posts) for name in cats}
    for cat_slug, path, base in pages:
        name = next((n for n, s in cats.items() if s == cat_slug), None)
        items = [p for p in posts if not name or p["cat"] == name]
        chips = [(None, "Все", len(posts))] + [(s, n, counts[n]) for n, s in cats.items()]
        chips_html = "".join(
            f'\n      <li><a class="chip" href="{base}{"category/" + s + ".html" if s else "index.html"}"'
            f'{" aria-current=\"page\"" if s == cat_slug else ""}>{n}<span class="chip__count">{c}</span></a></li>'
            for s, n, c in chips)
        cards = "".join(render_card(p, base, eager=i < 3) for i, p in enumerate(items[:PER_PAGE]))
        left = len(items) - PER_PAGE
        repl = {
            "{{BASE}}": base,
            "{{DOC_TITLE}}": f"{name} — блог Просебя" if name else "Блог о поддержке сотрудников — Просебя",
            "{{DESCRIPTION}}": escape(CATEGORY_LEADS.get(cat_slug, BLOG_LEAD)),
            "{{CRUMB_HIDDEN}}": "" if name else " hidden",
            "{{TITLE}}": escape(name or "Блог"),
            "{{LEAD}}": escape(CATEGORY_LEADS.get(cat_slug, BLOG_LEAD)),
            "{{CHIPS}}": chips_html,
            "{{CARDS}}": cards,
            "{{MORE_HIDDEN}}": "" if left > 0 else " hidden",
            "{{MORE_LABEL}}": f"Показать ещё {min(left, PER_PAGE)}" if left > 0 else "Показать ещё",
            "{{CAT_NAME}}": name or "",
        }
        page = shell
        for k, v in repl.items():
            page = page.replace(k, v)
        assert "{{" not in page, re.findall(r"\{\{\w+\}\}", page)
        path.write_text(page)
    print(f"Листинг и {len(cats)} {plural(len(cats), 'категория', 'категории', 'категорий')}: index.html, category/")


def bust_cache():
    """Метка версии у стилей и скриптов (?v=<хеш содержимого>): после обновления браузер
    не возьмёт из кэша старый файл к новой странице. GitHub Pages кэширует файлы на 10 минут."""
    versions = {}
    for name in ("blog.css", "blog.js", "posts.js"):
        versions[name] = hashlib.md5((ROOT / "assets" / name).read_bytes()).hexdigest()[:8]
    pages = [ROOT / "index.html", ROOT / "card.html", ROOT / "article-blocks.html",
             *sorted((ROOT / "category").glob("*.html")), *sorted(OUT.glob("*.html"))]
    for page in pages:
        html = page.read_text()
        for name, v in versions.items():
            html = re.sub(rf'(assets/{re.escape(name)})(\?v=\w+)?"', rf'\1?v={v}"', html)
        page.write_text(html)


def build():
    posts = load_posts()
    cats = categories()
    slugs = {p["slug"] for p in posts}
    headers = json.loads((ROOT / "content" / "table-headers.json").read_text())
    shell = (ROOT / "tools" / "article-shell.html").read_text().split("-->\n", 1)[1]
    OUT.mkdir(exist_ok=True)
    report = []

    # 1-й проход: разбор текста и время чтения (нужно карточкам)
    parsed = {}
    for post in posts:
        slug = post["slug"]
        blocks = parse((RAW / f"{slug}.html").read_text(), slugs)
        dropped_lead = False
        if blocks and blocks[0][0] == "p" and plain(blocks[0][1]).rstrip(".") == post["excerpt"].rstrip("."):
            blocks = blocks[1:]  # лид не повторяем в тексте
            dropped_lead = True
        last_h2 = max(i for i, b in enumerate(blocks) if b[0] == "h2")  # реклама Просебя → CTA
        post["read"] = reading_minutes(blocks[:last_h2])
        parsed[slug] = (blocks, last_h2, dropped_lead)

    # 2-й проход: страницы статей
    for post in posts:
        slug = post["slug"]
        blocks, last_h2, dropped_lead = parsed[slug]
        meta = json.loads((META / f"{slug}.json").read_text())
        cta_title = blocks[last_h2][1]
        cta_paras = [v for k, v in blocks[last_h2 + 1:] if k == "p"]
        cta_lists = [v for k, v in blocks[last_h2 + 1:] if k in ("ul", "ol")]
        body_blocks = blocks[:last_h2]

        prose, toc = render_blocks(body_blocks, slug, headers.get(slug))
        sources = sources_from(body_blocks)

        toc_items = "".join(f'\n          <li><a href="#{i}">{escape(t)}</a></li>' for i, t in toc) + "\n        "
        sources_html = ""
        if sources:
            items = "".join(
                f'\n          <li><span><a href="{escape(h)}">{escape(n)}</a>'
                + (f' <span class="sources__ctx">— {escape(c)}</span>' if c and c.lower() != n.lower() else "")
                + "</span></li>"
                for h, n, c in sources)
            sources_html = f"""
      <section class="sources" aria-labelledby="sources-title">
        <h2 id="sources-title">Источники</h2>
        <ol>{items}
        </ol>
      </section>
"""
        cta_body = "".join(f"\n          <p>{p}</p>" for p in cta_paras)
        cta_list = ""
        if cta_lists:
            cta_list = "\n        <ul>" + "".join(f"<li>{i}</li>" for lst in cta_lists for i in lst) + "</ul>"
        related = [p for p in posts if p["cat"] == post["cat"] and p["slug"] != slug][:3]

        page = shell
        repl = {
            "{{SEO_TITLE}}": escape(meta["seo_title"] or post["title"]),
            "{{SEO_DESCRIPTION}}": escape(meta["seo_description"] or post["excerpt"]),
            "{{SLUG}}": slug,
            "{{CAT}}": escape(post["cat"]),
            "{{CAT_SLUG}}": cats.get(post["cat"], ""),
            "{{TITLE}}": escape(post["title"]),
            "{{LEAD}}": escape(post["excerpt"]),
            "{{DATE_ISO}}": post["date"],
            "{{DATE}}": fmt_date(post["date"]),
            "{{READ}}": f"{post['read']} мин",
            "{{TOC_COUNT}}": str(len(toc)),
            "{{TOC_ITEMS}}": toc_items,
            "{{PROSE}}": prose,
            "{{SOURCES}}": sources_html,
            "{{CTA_TITLE}}": cta_title,
            "{{CTA_BODY}}": cta_body,
            "{{CTA_LIST}}": cta_list,
            "{{RELATED}}": "".join(render_card(p, "../") for p in related),
            "{{ICON_DATE}}": ICON_DATE,
            "{{ICON_TIME}}": ICON_TIME,
            "{{ICON_ARROW}}": ICON_ARROW,
            "{{ICON_CHEVRON}}": ICON_CHEVRON,
        }
        for k, v in repl.items():
            page = page.replace(k, v)
        assert "{{" not in page, re.findall(r"\{\{\w+\}\}", page)
        (OUT / f"{slug}.html").write_text(page)
        tables = sum(1 for b in body_blocks if b[0] == "table")
        report.append(f"{slug}: {len(toc)} разд., {post['read']} мин, табл. {tables}, источн. {len(sources)}"
                      + (", лид-дубль убран" if dropped_lead else ""))

    # время чтения → posts.js (для карточек, которые дописывает «Показать ещё»)
    js_path = ROOT / "assets" / "posts.js"
    js = js_path.read_text()
    for post in posts:
        js = re.sub(rf'(slug: "{re.escape(post["slug"])}",[^\n]*?read: )\d+', rf"\g<1>{post['read']}", js)
    js_path.write_text(js)

    build_listings(posts, cats)
    bust_cache()
    print("\n".join(report))
    print(f"\nГотово: {len(posts)} статей в {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    build()
