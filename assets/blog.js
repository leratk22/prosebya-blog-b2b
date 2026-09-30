/* Просебя · b2b-блог · поведение страниц.
   В WordPress карточки и страницы отдаёт сервер; здесь JS только имитирует это для демо. */
(() => {
  const CDN = "https://optim.tildacdn.com/";
  const PER_PAGE = 12;
  const LOAD_DELAY = 700; // имитация сети
  const PLACEHOLDER =
    '<svg viewBox="0 0 416 312" preserveAspectRatio="xMidYMid slice" aria-hidden="true">' +
    '<path d="M-20 230 C 60 120, 140 80, 190 150 C 240 220, 170 290, 130 230 C 90 170, 210 60, 290 90 C 370 120, 380 220, 440 180" ' +
    'fill="none" stroke="#FEDB50" stroke-width="44" stroke-linecap="round"/></svg>';
  const ICON_DATE =
    '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="1.75" y="2.75" width="10.5" height="9.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M1.75 5.75H12.25M4.75 1.5V3.5M9.25 1.5V3.5" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round"/></svg>';
  const ICON_TIME =
    '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" stroke-width="1.25"/><path d="M7 4.2V7L8.8 8.2" fill="none" stroke="currentColor" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  // Страницы статей лежат в blog/<slug>.html; страницы внутри blog/ задают window.BLOG_BASE = "../".
  // В WordPress адрес будет /blog-b2b/<slug>/
  const cardHref = post => `${window.BLOG_BASE || ""}blog/${post.slug}.html`;

  const fmtDate = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  const formatDate = iso => fmtDate.format(new Date(iso)).replace(/\s?г\.$/, "");

  function plural(n, one, few, many) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  function coverUrl(img) {
    const [dir, name] = img.split("/");
    return `${CDN}${dir}/-/format/webp/${name}.webp`; // WebP вместо PNG 1680 px: ~150 КБ вместо ~2,5 МБ
  }

  function renderCard(post, { index = 0, isNew = false } = {}) {
    const li = document.createElement("li");
    li.className = "card" + (isNew ? " is-new" : "");
    if (isNew) li.style.setProperty("--i", index);
    li.innerHTML = `
      <div class="card__cover${post.framed ? " card__cover--framed" : ""}"></div>
      <div class="card__category"></div>
      <h3 class="card__title"><a class="card__link" href="${cardHref(post)}"></a></h3>
      <p class="card__excerpt"></p>
      <div class="card__meta">
        <span>${ICON_DATE}<time datetime="${post.date}"></time></span>
        <span>${ICON_TIME}<span></span></span>
      </div>`;
    const cover = li.querySelector(".card__cover");
    if (post.img) {
      const img = new Image(416, 312);
      img.alt = "";
      img.loading = "lazy";
      img.decoding = "async";
      img.addEventListener("load", () => img.classList.add("is-loaded"), { once: true });
      img.src = coverUrl(post.img);
      cover.append(img);
      if (img.complete && img.naturalWidth) img.classList.add("is-loaded");
    } else {
      cover.innerHTML = PLACEHOLDER;
    }
    li.querySelector(".card__category").textContent = post.cat;
    li.querySelector(".card__link").textContent = post.title;
    li.querySelector(".card__excerpt").textContent = post.excerpt;
    li.querySelector("time").textContent = formatDate(post.date);
    li.querySelector(".card__meta > span:last-child > span").textContent = `${post.read} мин`;
    return li;
  }

  function renderSkeleton() {
    const li = document.createElement("li");
    li.className = "card card--skeleton";
    li.setAttribute("aria-hidden", "true");
    li.innerHTML =
      '<div class="sk sk--cover"></div><div class="sk sk--label"></div>' +
      '<div class="sk sk--title"></div><div class="sk sk--title2"></div><div class="sk sk--meta"></div>';
    return li;
  }

  /* Лента с «Показать ещё»: карточки дописываются, адрес меняется на ?page=N.
     В WordPress: кнопка — ссылка на /blog-b2b/page/N/, JS перехватывает клик и делает то же самое. */
  function mountFeed({ list, posts, button, moreWrap, pageOffset = 0, onPage }) {
    // pageOffset — сколько страниц пропущено при прямом заходе на ?page=N
    let page = 1;
    const pages = Math.ceil(posts.length / PER_PAGE);
    const pageUrl = n => urlForPage(n + pageOffset);

    list.append(...posts.slice(0, page * PER_PAGE).map(p => renderCard(p)));
    const update = () => {
      const left = posts.length - page * PER_PAGE;
      moreWrap.hidden = left <= 0;
      button.textContent = `Показать ещё ${Math.min(left, PER_PAGE)}`;
      button.href = pageUrl(page + 1);
    };
    update();

    button.addEventListener("click", e => {
      e.preventDefault();
      if (button.getAttribute("aria-busy") === "true" || page >= pages) return;
      const next = posts.slice(page * PER_PAGE, (page + 1) * PER_PAGE);
      button.setAttribute("aria-busy", "true");
      button.textContent = "Загружаем…";
      const skeletons = next.map(renderSkeleton);
      list.append(...skeletons);
      setTimeout(() => {
        skeletons.forEach(s => s.remove());
        const cards = next.map((p, i) => renderCard(p, { index: i, isNew: true }));
        list.append(...cards);
        page += 1;
        history.pushState({ page }, "", pageUrl(page));
        button.removeAttribute("aria-busy");
        update();
        // фокус на первую новую карточку — для клавиатуры и скринридеров
        cards[0].querySelector(".card__link").focus({ preventScroll: true });
        onPage && onPage(page);
      }, LOAD_DELAY);
    });
  }

  function urlForPage(page) {
    const url = new URL(location.href);
    if (page > 1) url.searchParams.set("page", page); else url.searchParams.delete("page");
    return url.pathname + url.search;
  }

  /* Шапка: линия снизу после прокрутки; мобильное меню */
  function mountHeader() {
    const header = document.querySelector(".site-header");
    if (header) {
      const onScroll = () => header.classList.toggle("is-scrolled", scrollY > 4);
      addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    }
    const menu = document.getElementById("mobile-menu");
    const openBtn = document.querySelector("[data-menu-open]");
    const closeBtn = document.querySelector("[data-menu-close]");
    if (!menu || !openBtn) return;
    const setOpen = open => {
      menu.classList.toggle("is-open", open);
      menu.inert = !open;
      openBtn.setAttribute("aria-expanded", String(open));
      document.body.style.overflow = open ? "hidden" : "";
      (open ? closeBtn : openBtn).focus();
    };
    menu.inert = true;
    openBtn.addEventListener("click", () => setOpen(true));
    closeBtn.addEventListener("click", () => setOpen(false));
    addEventListener("keydown", e => { if (e.key === "Escape" && menu.classList.contains("is-open")) setOpen(false); });
  }

  /* ---------- Статья ---------- */
  function mountArticle({ body, progress }) {
    // Прогресс чтения: доля пройденного текста статьи, без анимации
    if (progress && body) {
      const update = () => {
        const r = body.getBoundingClientRect();
        const total = r.height - innerHeight * 0.5;
        const p = Math.min(1, Math.max(0, -r.top / total));
        progress.style.transform = `scaleX(${p})`;
      };
      addEventListener("scroll", update, { passive: true });
      addEventListener("resize", update);
      update();
    }

    // Оглавление: подсветка текущего раздела
    const tocLinks = [...document.querySelectorAll(".toc__list a")];
    const headings = tocLinks.map(a => document.getElementById(a.hash.slice(1))).filter(Boolean);
    if (headings.length) {
      const setCurrent = id => tocLinks.forEach(a => a.setAttribute("aria-current", String(a.hash === "#" + id)));
      const spy = () => {
        const line = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-height")) + 120;
        let current = headings[0];
        for (const h of headings) if (h.getBoundingClientRect().top <= line) current = h;
        setCurrent(current.id);
      };
      addEventListener("scroll", spy, { passive: true });
      spy();
    }

    // Мобильное оглавление закрывается после перехода
    document.querySelectorAll(".toc-mobile a").forEach(a =>
      a.addEventListener("click", () => a.closest("details").removeAttribute("open")));

    // «Скопировать ссылку»: на 2 с показываем «Ссылка скопирована»
    document.querySelectorAll("[data-copy-link]").forEach(btn => {
      let timer;
      btn.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(location.href.split("#")[0]); } catch (e) { /* нет доступа — всё равно покажем состояние */ }
        btn.classList.add("is-done");
        clearTimeout(timer);
        timer = setTimeout(() => btn.classList.remove("is-done"), 2000);
      });
    });

    // Таблица: скопировать (TSV — вставляется в Excel/Google Таблицы) и скачать CSV
    document.querySelectorAll(".table-block").forEach(block => {
      const rows = () => [...block.querySelectorAll("tr")].map(tr => [...tr.cells].map(c => c.innerText.trim()));
      block.querySelector("[data-table-copy]")?.addEventListener("click", async e => {
        const btn = e.currentTarget;
        try { await navigator.clipboard.writeText(rows().map(r => r.join("\t")).join("\n")); } catch (err) {}
        const label = btn.querySelector("span");
        const old = label.textContent;
        label.textContent = "Таблица скопирована";
        setTimeout(() => (label.textContent = old), 2000);
      });
      block.querySelector("[data-table-csv]")?.addEventListener("click", () => {
        const csv = rows().map(r => r.map(c => `"${c.replace(/"/g, '""')}"`).join(";")).join("\r\n");
        const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
        const a = Object.assign(document.createElement("a"), { href: url, download: (block.dataset.name || "table") + ".csv" });
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
    });
  }

  window.Blog = { renderCard, renderSkeleton, mountFeed, mountHeader, mountArticle, plural, PER_PAGE };
})();
