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
  const SPORTS = ['NFL', 'CFB', 'NBA', 'NCAAB'];
  const BOOSTS = [0, 25, 30, 50, 100];
  return { fmtOdds, pct, signedPct, money, fair, price, rungLabel, sideProbs, when, stamp, load, esc, SPORTS, BOOSTS };
})();
