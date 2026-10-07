// Tema do site: claro, escuro ou automático (segue o aparelho). Carregado no <head>, antes da página,
// para aplicar o tema escolhido sem piscar. A escolha fica no navegador do visitante (localStorage).
(() => {
  const raiz = document.documentElement;
  const ler = () => { try { return localStorage.getItem('tema'); } catch (e) { return null; } };
  const aplicar = (pref) => {
    if (pref === 'light' || pref === 'dark') raiz.dataset.theme = pref; else delete raiz.dataset.theme;
    raiz.dataset.pref = pref === 'light' || pref === 'dark' ? pref : 'auto';
  };
  aplicar(ler());

  document.addEventListener('DOMContentLoaded', () => {
    const menu = document.querySelector('.temasw');
    if (!menu) return;
    const marcar = () => menu.querySelectorAll('[data-tema]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.tema === raiz.dataset.pref)));
    marcar();
    menu.addEventListener('click', (e) => {
      const b = e.target.closest('[data-tema]');
      if (!b) return;
      const pref = b.dataset.tema;
      try { if (pref === 'auto') localStorage.removeItem('tema'); else localStorage.setItem('tema', pref); } catch (err) { /* sem armazenamento: vale só nesta página */ }
      aplicar(pref);
      marcar();
      menu.open = false;
    });
    // fecha os menus do header (tema e idioma) ao clicar fora
    document.addEventListener('click', (e) => document.querySelectorAll('header.site details[open]').forEach((d) => { if (!d.contains(e.target)) d.open = false; }));
  });
})();
