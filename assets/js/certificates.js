'use strict';

// Certificates tab: topic filter, "show all", and an accessible lightbox.
(function () {
  const root = document.querySelector('[data-certs]');
  const box = document.querySelector('[data-cert-lightbox]');
  if (!root || !box) return;

  const INITIAL = 12;
  const cards = Array.from(root.querySelectorAll('.cert-card'));
  const filters = Array.from(root.querySelectorAll('[data-cert-filter]'));
  const moreBtn = root.querySelector('[data-certs-more]');
  let topic = 'all';
  let expanded = false;

  function render() {
    let shown = 0;
    cards.forEach(function (card) {
      const match = topic === 'all' || card.dataset.topic === topic;
      const visible = match && (topic !== 'all' || expanded || shown < INITIAL);
      if (match && visible) shown++;
      card.hidden = !visible;
    });
    if (moreBtn) moreBtn.hidden = topic !== 'all' || expanded || cards.length <= INITIAL;
  }

  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      topic = btn.dataset.certFilter;
      filters.forEach(function (b) {
        const on = b === btn;
        b.classList.toggle('is-active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      render();
    });
  });

  if (moreBtn) {
    moreBtn.addEventListener('click', function () {
      expanded = true;
      const first = cards.filter(function (c) { return c.hidden; })[0];
      render();
      moreBtn.setAttribute('aria-expanded', 'true');
      const btn = first && first.querySelector('[data-cert-open]');
      if (btn) btn.focus({ preventScroll: true });
    });
  }
  render();

  // Lightbox
  document.body.appendChild(box);
  const img = box.querySelector('[data-lb-img]');
  const title = box.querySelector('[data-lb-title]');
  const org = box.querySelector('[data-lb-org]');
  const date = box.querySelector('[data-lb-date]');
  const count = box.querySelector('[data-lb-count]');
  const links = box.querySelector('[data-lb-links]');
  const dialog = box.querySelector('.cert-lightbox-dialog');
  let list = [];
  let index = 0;
  let opener = null;
  let saved = null;

  function show(i) {
    index = (i + list.length) % list.length;
    const c = list[index];
    const d = c.dataset;
    img.removeAttribute('src');
    img.width = +d.largeW;
    img.height = +d.largeH;
    img.srcset = d.srcset;
    img.sizes = '(min-width: 1140px) 1060px, 100vw';
    img.src = d.large;
    img.alt = c.querySelector('.cert-thumb img').alt;
    title.textContent = c.querySelector('.cert-title').textContent;
    org.textContent = c.querySelector('.cert-org').textContent;
    date.textContent = c.querySelector('.cert-date time').textContent;
    date.setAttribute('datetime', c.querySelector('.cert-date time').getAttribute('datetime'));
    count.textContent = (index + 1) + ' of ' + list.length;
    links.innerHTML = c.querySelector('.cert-links').innerHTML;
  }

  function open(card) {
    list = cards.filter(function (c) { return topic === 'all' || c.dataset.topic === topic; });
    opener = document.activeElement;
    saved = [document.documentElement.style.overflow, document.body.style.overflow];
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    show(list.indexOf(card));
    box.hidden = false;
    box.querySelector('[data-lb-close]').focus();
  }

  function close() {
    if (box.hidden) return;
    box.hidden = true;
    img.removeAttribute('src');
    img.removeAttribute('srcset');
    document.documentElement.style.overflow = saved ? saved[0] : '';
    document.body.style.overflow = saved ? saved[1] : '';
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
  }

  root.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-cert-open]');
    if (btn) open(btn.closest('.cert-card'));
  });
  box.querySelector('[data-lb-close]').addEventListener('click', close);
  box.querySelector('[data-lb-prev]').addEventListener('click', function () { show(index - 1); });
  box.querySelector('[data-lb-next]').addEventListener('click', function () { show(index + 1); });
  box.addEventListener('click', function (e) { if (!dialog.contains(e.target)) close(); });

  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); show(index - 1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); show(index + 1); }
    else if (e.key === 'Tab') {
      const f = Array.from(dialog.querySelectorAll('a[href], button:not([disabled])'))
        .filter(function (el) { return el.offsetParent !== null; });
      if (!f.length) return;
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
    }
  });
})();
