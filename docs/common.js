// Shared math and helpers for the Prop Ladder pages.
const PL = (() => {
  const fmtOdds = (a) => (a > 0 ? '+' : '') + a;
  const pct = (p, d = 1) => (p * 100).toFixed(d) + '%';
  const signedPct = (x) => (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x * 100).toFixed(1) + '%';
  const money = (x) => (x >= 0 ? '+$' : '−$') + Math.abs(x).toFixed(2);
  const fair = (p) => { const v = p >= 0.5 ? -100 * p / (1 - p) : 100 * (1 - p) / p; return fmtOdds(Math.round(v)); };

  // Price one side of one rung at one book. pW win, pL lose (a push is neither).
  // boost = profit boost as a fraction (0.25 = 25%). Stake $10.
  function price(a, pW, pL, boost) {
    const profit = (a > 0 ? a / 10 : 1000 / -a) * (1 + boost);
    const be = 10 / (10 + profit);            // book's implied (break-even) probability
    const pTrue = pW / Math.max(pW + pL, 1e-9); // true probability, pushes removed
    return { be, pTrue, edge: pTrue - be, ev: pW * profit - pL * 10 };
  }

  function rungLabel(line, side) {
    if (Number.isInteger(line)) return (side === 'o' ? 'Over ' : 'Under ') + line;
    return side === 'o' ? Math.ceil(line) + '+' : Math.floor(line) + ' or fewer';
  }
  function sideProbs(r, side) {
    const push = r.pp || 0;
    return side === 'o' ? { pW: r.po, pL: r.pu } : { pW: r.pu, pL: r.po, push };
  }
  const when = (iso) => iso ? new Date(iso).toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: '2-digit' }) : '';
  const stamp = (iso) => 'Prices pulled ' + new Date(iso).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' ET';

  async function load() {
    const r = await fetch('data.json', { cache: 'no-store' });
    if (!r.ok) throw new Error('data.json ' + r.status);
    return r.json();
  }
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Sortable tables. Each row carries k: {columnKey: value}; nulls sort last.
  function sortRows(rows, sort) {
    return rows.slice().sort((a, b) => {
      const x = a.k[sort.key], y = b.k[sort.key];
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      const c = typeof x === 'string' ? x.localeCompare(y) : x - y;
      return sort.dir === 'asc' ? c : -c;
    });
  }
  // th[data-k] become sort buttons; data-first="asc" for text-like columns.
  function sortHeaders(tr, S, render) {
    tr.querySelectorAll('th[data-k]').forEach((th) => {
      const k = th.dataset.k;
      if (!th.dataset.label) th.dataset.label = th.textContent.trim();
      const on = S.sort.key === k;
      th.setAttribute('aria-sort', on ? (S.sort.dir === 'asc' ? 'ascending' : 'descending') : 'none');
      th.innerHTML = `<button type="button" class="sort">${th.dataset.label}<span class="arr" aria-hidden="true">${on ? (S.sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}</span></button>`;
      th.querySelector('button').onclick = () => {
        S.sort = on ? { key: k, dir: S.sort.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: th.dataset.first || 'desc' };
        render();
      };
    });
  }
  const payout = (a) => a > 0 ? 1 + a / 100 : 1 + 100 / -a;   // decimal odds, for sorting prices
  const SPORTS = ['NFL', 'CFB', 'NBA', 'NCAAB'];
  const BOOSTS = [0, 25, 30, 50, 100];
  return { sortRows, sortHeaders, payout, fmtOdds, pct, signedPct, money, fair, price, rungLabel, sideProbs, when, stamp, load, esc, SPORTS, BOOSTS };
})();
