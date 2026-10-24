// Scroll areas that continue below the fold fade out at the bottom edge, so cut-off content reads as "more".
const SEL = ".panel-body, .sheet, .inspector";

function update(el: Element) {
  const e = el as HTMLElement;
  e.classList.toggle("more", e.scrollTop + e.clientHeight < e.scrollHeight - 8);
}

export function installScrollHints() {
  const seen = new WeakSet<Element>();
  const ro = new ResizeObserver((xs) => xs.forEach((x) => update(x.target)));
  const scan = () => document.querySelectorAll(SEL).forEach((el) => {
    if (!seen.has(el)) {
      seen.add(el);
      el.addEventListener("scroll", () => update(el), { passive: true });
      ro.observe(el);
    }
    update(el);
  });
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  scan();
}
