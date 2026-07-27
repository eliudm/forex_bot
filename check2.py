with open('dashboard/live_dashboard.html', 'r', encoding='utf-8') as f:
    code = f.read()

if 'Promise.all' in code:
    start = code.find('async function fetchAll()')
    end   = code.find('\n}', start) + 2
    new_fn = """async function fetchAll() {
  const safe = async (url, fb) => {
    try { const r = await fetch(url); return r.ok ? await r.json() : fb; }
    catch(e) { return fb; }
  };
  const status  = await safe('/api/status',  {status:'OFFLINE',status_reason:'Cannot reach server'});
  const stats   = await safe('/api/stats',   {balance:0,total_pnl:0,return_pct:0,total_trades:0,wins:0,losses:0,win_rate:0,open_trades:0});
  const signals = await safe('/api/signals', {});
  const equity  = await safe('/api/equity',  [{t:'Start',v:0}]);
  const log     = await safe('/api/log',     []);
  isLive = status.status !== 'OFFLINE';
  updateHeader(isLive);
  updateCards(stats);
  updateStatus(status);
  updateMarkets(signals);
  updateChart(equity, stats.balance);
  updateLog(log);
}"""
    code = code[:start] + new_fn + code[end:]
    with open('dashboard/live_dashboard.html', 'w', encoding='utf-8') as f:
        f.write(code)
    print('FIXED successfully')
else:
    print('Already has fix applied - file size:', len(code))