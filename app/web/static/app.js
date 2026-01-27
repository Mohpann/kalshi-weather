async function loadSnapshot() {
  const statusEl = document.querySelector('[data-field="status"]');
  const weatherEl = document.querySelector('[data-field="weather"]');
  const subtitleEl = document.querySelector('[data-field="subtitle"]');
  const exchangeEl = document.querySelector('[data-field="exchange"]');
  const eventMarketsEl = document.querySelector('[data-field="event-markets"]');
  const eventTickerEl = document.querySelector('[data-field="event-ticker"]');
  const updatedEl = document.querySelector('[data-field="updated"]');
  const healthEl = document.querySelector('[data-field="health"]');
  const modelsEl = document.querySelector('[data-field="models"]');
  const forecastHighEl = document.querySelector('[data-field="forecast-high"]');
  const opportunitiesEl = document.querySelector('[data-field="opportunities"]');
  const portfolioEl = document.querySelector('[data-field="portfolio"]');
  const cashEl = document.querySelector('[data-field="cash"]');
  const ordersNoteEl = document.querySelector('[data-field="orders-note"]');
  const positionsEl = document.querySelector('[data-field="positions"]');
  const ordersEl = document.querySelector('[data-field="orders"]');

  try {
    const response = await fetch('/api/snapshot');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();

    if (data.error) {
      throw new Error(data.error);
    }

    if (statusEl) {
      statusEl.textContent = data.market?.status ?? 'unknown';
    }
    if (data.weather) {
      const current = data.weather.current_temp != null ? `${data.weather.current_temp}°F` : '—';
      const high = data.weather.high_today != null ? `${data.weather.high_today}°F` : '—';
      weatherEl.textContent = `${current} / ${high}`;
    } else {
      weatherEl.textContent = '—';
    }
    if (exchangeEl) {
      const ex = data.exchange ?? {};
      const exActive = ex.exchange_active === true ? 'active' : 'inactive';
      const trActive = ex.trading_active === true ? 'trading' : 'paused';
      exchangeEl.textContent = `${exActive} · ${trActive}`;
    }

    if (data.market?.title) {
      subtitleEl.textContent = data.market.title;
    } else if (data.event_ticker) {
      subtitleEl.textContent = `Tracking ${data.event_ticker} markets`;
    }

    if (updatedEl) {
      if (data.timestamp) {
        const date = new Date(data.timestamp);
        if (Number.isNaN(date.getTime())) {
          updatedEl.textContent = data.timestamp;
        } else {
          updatedEl.textContent = date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
          });
        }
      } else {
        updatedEl.textContent = '—';
      }
    }
    if (healthEl) {
      let ageText = 'age —';
      if (data.timestamp) {
        const date = new Date(data.timestamp);
        if (!Number.isNaN(date.getTime())) {
          const ageSeconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
          if (ageSeconds < 60) {
            ageText = `${ageSeconds}s`;
          } else if (ageSeconds < 3600) {
            ageText = `${Math.floor(ageSeconds / 60)}m`;
          } else {
            ageText = `${Math.floor(ageSeconds / 3600)}h`;
          }
        }
      }
      const source = data.weather?.source || 'unknown';
      healthEl.textContent = `source ${source} · age ${ageText}`;
    }
    if (modelsEl) {
      const gfs = data.open_meteo?.gfs_high;
      const ecmwf = data.open_meteo?.ecmwf_high;
      const spread = data.open_meteo?.spread;
      const gfsText = gfs != null ? `NOAA GFS ${gfs.toFixed(1)}°F` : 'NOAA GFS —';
      const ecmwfText = ecmwf != null ? `ECMWF (European) ${ecmwf.toFixed(1)}°F` : 'ECMWF (European) —';
      const spreadText = spread != null ? `Δ ${spread.toFixed(1)}°` : 'Δ —';
      modelsEl.textContent = `${gfsText} · ${ecmwfText} · ${spreadText}`;
    }
    if (forecastHighEl) {
      const gfs = data.open_meteo?.gfs_high;
      const ecmwf = data.open_meteo?.ecmwf_high;
      if (gfs != null && ecmwf != null) {
        const maxHigh = Math.max(gfs, ecmwf);
        forecastHighEl.textContent = `NOAA GFS ${gfs.toFixed(1)}°F / ECMWF (European) ${ecmwf.toFixed(1)}°F (top ${maxHigh.toFixed(1)}°F)`;
      } else if (gfs != null) {
        forecastHighEl.textContent = `NOAA GFS ${gfs.toFixed(1)}°F`;
      } else if (ecmwf != null) {
        forecastHighEl.textContent = `ECMWF (European) ${ecmwf.toFixed(1)}°F`;
      } else {
        forecastHighEl.textContent = '—';
      }
    }
    if (portfolioEl) {
      const portfolioValue = data.portfolio?.portfolio_value;
      const balance = data.portfolio?.balance;
      if (typeof portfolioValue === 'number') {
        portfolioEl.textContent = `$${(portfolioValue / 100).toFixed(2)}`;
      } else if (typeof balance === 'number') {
        portfolioEl.textContent = `$${(balance / 100).toFixed(2)}`;
      } else {
        portfolioEl.textContent = '—';
      }
    }
    if (cashEl) {
      const balance = data.portfolio?.balance;
      if (typeof balance === 'number') {
        cashEl.textContent = `$${(balance / 100).toFixed(2)}`;
      } else {
        cashEl.textContent = '—';
      }
    }
    if (ordersNoteEl) {
      ordersNoteEl.textContent = data.orders_note || '—';
    }

    if (opportunitiesEl) {
      opportunitiesEl.innerHTML = '';
      const markets = data.event_markets ?? [];
      const gfs = data.open_meteo?.gfs_high;
      const ecmwf = data.open_meteo?.ecmwf_high;
      const forecast = gfs != null && ecmwf != null ? (gfs + ecmwf) / 2 : (gfs ?? ecmwf);

      const parseCondition = (title) => {
        if (!title) return null;
        const temps = title.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
        const lower = title.toLowerCase();
        if (temps.length >= 2 && (lower.includes('between') || lower.includes(' to '))) {
          const low = Math.min(temps[0], temps[1]);
          const high = Math.max(temps[0], temps[1]);
          return { type: 'range', low, high };
        }
        if (lower.includes('>') || lower.includes('greater than') || lower.includes('above')) {
          return { type: 'gt', threshold: temps[0] };
        }
        if (lower.includes('<') || lower.includes('less than') || lower.includes('below')) {
          return { type: 'lt', threshold: temps[0] };
        }
        return null;
      };

      const opportunities = [];
      if (forecast != null) {
        markets.forEach((m) => {
          const condition = parseCondition(m.title);
          if (!condition) return;
          const price = m.last_price;
          if (price == null) return;

          let shouldBuy = false;
          let reason = '';
          if (condition.type === 'gt') {
            if (forecast >= condition.threshold + 1 && price <= 60) {
              shouldBuy = true;
              reason = `Forecast high ~${forecast.toFixed(1)}°F above ${condition.threshold}°F`;
            }
          } else if (condition.type === 'lt') {
            if (forecast <= condition.threshold - 1 && price <= 70) {
              shouldBuy = true;
              reason = `Forecast high ~${forecast.toFixed(1)}°F below ${condition.threshold}°F`;
            }
          } else if (condition.type === 'range') {
            if (forecast >= condition.low - 0.5 && forecast <= condition.high + 0.5 && price <= 60) {
              shouldBuy = true;
              reason = `Forecast high ~${forecast.toFixed(1)}°F inside ${condition.low}-${condition.high}°F`;
            }
          }

          if (shouldBuy) {
            opportunities.push({
              ticker: m.ticker,
              title: m.title,
              price,
              reason,
            });
          }
        });
      }

      if (!opportunities.length) {
        const empty = document.createElement('div');
        empty.className = 'opportunities__row';
        empty.textContent = 'No opportunities yet';
        opportunitiesEl.appendChild(empty);
      } else {
        opportunities.forEach((o) => {
          const row = document.createElement('div');
          row.className = 'opportunities__row';
          const title = document.createElement('div');
          title.className = 'opportunities__title';
          title.textContent = `Buy YES · ${o.ticker} · ${o.price}¢`;
          const meta = document.createElement('div');
          meta.className = 'opportunities__meta';
          meta.textContent = `${o.title} — ${o.reason}`;
          row.appendChild(title);
          row.appendChild(meta);
          opportunitiesEl.appendChild(row);
        });
      }
    }

    if (positionsEl) {
      positionsEl.innerHTML = '';
      const marketPositions = data.positions?.market_positions || [];
      const eventPositions = data.positions?.event_positions || [];
      const positions = data.positions?.positions || data.positions?.portfolio?.positions || data.positions?.data || [];
      const merged = positions.length ? positions : [...marketPositions, ...eventPositions];
      if (!merged.length) {
        const empty = document.createElement('div');
        empty.className = 'positions__row';
        empty.textContent = 'No positions loaded';
        positionsEl.appendChild(empty);
      } else {
        merged.forEach((pos) => {
          if (!pos) return;
          const row = document.createElement('div');
          row.className = 'positions__row';
          const ticker = document.createElement('span');
          ticker.textContent = pos.ticker ?? pos.event_ticker ?? '—';
          const net = document.createElement('span');
          const netVal = pos.position ?? pos.net_position ?? pos.count ?? pos.size ?? pos.total_cost_shares_fp ?? pos.total_cost_shares ?? 0;
          net.textContent = `Net: ${netVal}`;
          const pnl = document.createElement('span');
          const pnlVal = pos.unrealized_pnl ?? pos.realized_pnl ?? null;
          if (typeof pnlVal === 'number') {
            pnl.textContent = `PnL: ${(pnlVal / 100).toFixed(2)}`;
          } else {
            pnl.textContent = 'PnL: —';
          }
          row.appendChild(ticker);
          row.appendChild(net);
          row.appendChild(pnl);
          positionsEl.appendChild(row);
        });
      }
    }

    if (ordersEl) {
      ordersEl.innerHTML = '';
      const orders = data.orders?.orders || data.orders?.data || [];
      if (!orders.length) {
        const empty = document.createElement('div');
        empty.className = 'orders__row';
        empty.textContent = 'No orders loaded';
        ordersEl.appendChild(empty);
      } else {
        orders.slice(0, 20).forEach((order) => {
          const row = document.createElement('div');
          row.className = 'orders__row';
          const ticker = document.createElement('span');
          ticker.textContent = order.ticker ?? '—';
          const side = document.createElement('span');
          side.textContent = `${order.action ?? ''} ${order.side ?? ''}`.trim() || '—';
          const price = document.createElement('span');
          const priceVal = order.yes_price ?? order.no_price ?? order.price;
          price.textContent = priceVal != null ? `${priceVal}¢` : '—';
          const count = document.createElement('span');
          count.textContent = order.count != null ? `x${order.count}` : 'x—';
          row.appendChild(ticker);
          row.appendChild(side);
          row.appendChild(price);
          row.appendChild(count);
          ordersEl.appendChild(row);
        });
      }
    }

    if (eventTickerEl) {
      eventTickerEl.textContent = data.event_ticker ?? 'Event';
    }
    if (eventMarketsEl) {
      eventMarketsEl.innerHTML = '';
      const markets = data.event_markets ?? [];
      const orderbooks = data.event_orderbooks ?? [];
      const bookByTicker = {};
      orderbooks.forEach((book) => {
        if (book && book.ticker) {
          bookByTicker[book.ticker] = book;
        }
      });
      if (!markets.length) {
        const empty = document.createElement('div');
        empty.className = 'event-markets__row';
        empty.textContent = 'No data';
        eventMarketsEl.appendChild(empty);
      } else {
        markets.forEach((market) => {
          const card = document.createElement('div');
          card.className = 'event-market';

          const header = document.createElement('button');
          header.type = 'button';
          header.className = 'event-market__header';
          const ticker = document.createElement('span');
          ticker.textContent = market.ticker ?? '—';
          const title = document.createElement('span');
          title.textContent = market.title ?? '—';
          const status = document.createElement('span');
          status.textContent = market.status ?? '—';
          const price = document.createElement('span');
          price.textContent = market.last_price != null ? `${market.last_price}¢` : '—';
          header.appendChild(ticker);
          header.appendChild(title);
          header.appendChild(status);
          header.appendChild(price);

          const book = bookByTicker[market.ticker] || {};
          const bookWrap = document.createElement('div');
          bookWrap.className = 'event-market__books';

          const buildSide = (label, rows) => {
            const side = document.createElement('div');
            side.className = 'event-market__side';
            const sideLabel = document.createElement('div');
            sideLabel.className = 'event-market__side-label';
            sideLabel.textContent = label;
            side.appendChild(sideLabel);
            if (!rows || rows.length === 0) {
              const emptyRow = document.createElement('div');
              emptyRow.className = 'event-market__row';
              emptyRow.textContent = 'No data';
              side.appendChild(emptyRow);
            } else {
              rows.forEach((row) => {
                const line = document.createElement('div');
                line.className = 'event-market__row';
                const price = row.price != null ? `${row.price}¢` : '—';
                const count = row.count != null ? row.count : '—';
                line.textContent = `${price} · ${count}`;
                side.appendChild(line);
              });
            }
            return side;
          };

          bookWrap.appendChild(buildSide('YES', book.yes ?? []));
          bookWrap.appendChild(buildSide('NO', book.no ?? []));

          card.appendChild(header);
          card.appendChild(bookWrap);
          eventMarketsEl.appendChild(card);

          header.addEventListener('click', () => {
            card.classList.toggle('is-open');
          });
        });
      }
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = 'offline';
    }
    if (exchangeEl) {
      exchangeEl.textContent = 'unknown';
    }
    subtitleEl.textContent = 'Snapshot unavailable';
    if (modelsEl) {
      modelsEl.textContent = 'Models unavailable';
    }
    if (forecastHighEl) {
      forecastHighEl.textContent = '—';
    }
    if (healthEl) {
      healthEl.textContent = 'source unknown · age —';
    }
    if (portfolioEl) {
      portfolioEl.textContent = '—';
    }
    if (cashEl) {
      cashEl.textContent = '—';
    }
    if (ordersNoteEl) {
      ordersNoteEl.textContent = '—';
    }
    if (positionsEl) {
      positionsEl.textContent = 'No positions loaded';
    }
    if (ordersEl) {
      ordersEl.textContent = 'No orders loaded';
    }
    if (opportunitiesEl) {
      opportunitiesEl.textContent = 'No opportunities yet';
    }
    console.error(err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const refreshBtn = document.querySelector('[data-action="refresh"]');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', loadSnapshot);
  }
  loadSnapshot();
  setInterval(loadSnapshot, 15000);

  const logsEl = document.querySelector('[data-field="logs"]');
  if (logsEl) {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/logs`);
    ws.onmessage = (event) => {
      const line = document.createElement('div');
      line.className = 'logs__line';
      line.textContent = event.data;
      logsEl.appendChild(line);
      logsEl.scrollTop = logsEl.scrollHeight;
    };
    ws.onerror = () => {
      const line = document.createElement('div');
      line.className = 'logs__line';
      line.textContent = 'Log stream error.';
      logsEl.appendChild(line);
    };
  }
});
