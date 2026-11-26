import React, { useEffect, useId, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { request } from './api.js';
import { displayDate, money, parseDate, positiveDecimal, southAfricanToday } from './format.js';
import './style.css';

const nextStatus = {
  DRAFT: ['SENT', 'Mark sent'],
  SENT: ['EXECUTED', 'Execute'],
  EXECUTED: ['DONE', 'Mark done'],
};

function Select({ label, placeholder, value, onChange, children }) {
  const labelId = useId();
  return (
    <label>
      <span id={labelId}>{label}</span>
      <select aria-labelledby={labelId} required value={value} onChange={event => onChange(event.target.value)}>
        <option value="" disabled>{placeholder}</option>
        {children}
      </select>
    </label>
  );
}

function Warning({ trade }) {
  if (!trade.warning) return null;
  return <p className="warning">{trade.warning}</p>;
}

function Capture({ reference, instruments, today, onChange }) {
  const [form, setForm] = useState(() => ({
    date: displayDate(today), fund: '', instrument_id: '', side: '', qty: '', price: '', broker: '',
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState(null);
  const instrument = instruments.find(item => String(item.id) === form.instrument_id);
  const isFuture = instrument?.asset_class?.toUpperCase() === 'FUTURE';
  const set = field => value => setForm(previous => ({ ...previous, [field]: value }));

  async function submit(event) {
    event.preventDefault();
    setError('');
    setReceipt(null);
    const { date, instrument_id, qty, price, ...choices } = form;
    const trade_date = parseDate(date.trim());
    const quantity = qty.trim();
    const quotedPrice = price.trim();
    if (!trade_date) return setError('Enter a valid trade date in DD/MM/YYYY format.');
    if (!positiveDecimal(quantity) || !positiveDecimal(quotedPrice)) {
      return setError('Enter a positive quantity and price.');
    }
    if (isFuture && !/^\d+(?:\.0*)?$/.test(quantity)) {
      return setError('Enter a whole number of futures contracts.');
    }
    setSaving(true);
    try {
      const saved = await request('/trades', {
        method: 'POST',
        body: { ...choices, trade_date, instrument_id: Number(instrument_id), qty: quantity, price: quotedPrice },
      });
      setReceipt(saved);
      setForm(previous => ({ ...previous, side: '', broker: '', qty: '', price: '' }));
      onChange();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <fieldset disabled={saving}>
        <div className="fields">
          <label>
            Trade date
            <input required value={form.date} onChange={event => set('date')(event.target.value)}
              placeholder="DD/MM/YYYY" maxLength={10} />
          </label>
          <Select label="Fund" placeholder="Select fund" value={form.fund} onChange={set('fund')}>
            {reference.funds.map(fund => <option key={fund}>{fund}</option>)}
          </Select>
          <div className="wide">
            <Select label="Instrument" placeholder="Select instrument" value={form.instrument_id} onChange={set('instrument_id')}>
              {instruments.map(item => <option value={item.id} key={item.id}>{item.code} — {item.name}</option>)}
            </Select>
            {instrument && (
              <div className="instrument">
                <strong>{instrument.currency} · {instrument.quote_unit}</strong>
                <span>{instrument.last_close != null && instrument.last_close_date
                  ? 'Latest close ' + instrument.last_close + ' · ' + displayDate(instrument.last_close_date)
                  : 'Latest close unavailable'}</span>
              </div>
            )}
          </div>
          <Select label="Side" placeholder="Select side" value={form.side} onChange={set('side')}>
            <option value="BUY">Buy</option>
            <option value="SELL">Sell</option>
          </Select>
          <Select label="Broker" placeholder="Select broker" value={form.broker} onChange={set('broker')}>
            {reference.brokers.map(broker => <option key={broker}>{broker}</option>)}
          </Select>
          <label>
            {isFuture ? 'Contracts' : 'Quantity'}
            <input required inputMode={isFuture ? 'numeric' : 'decimal'} value={form.qty}
              onChange={event => set('qty')(event.target.value)} placeholder="0" />
          </label>
          <label>
            {instrument ? 'Price (' + instrument.quote_unit + ')' : 'Price'}
            <input required inputMode="decimal" value={form.price}
              onChange={event => set('price')(event.target.value)} placeholder="0.00" />
          </label>
        </div>
        <button className="primary" type="submit">{saving ? 'Saving draft…' : 'Capture draft'}</button>
      </fieldset>
      {error && <p className="error" role="alert">{error}</p>}
      {receipt && (
        <div className="receipt" role="status">
          Draft #{receipt.id} captured · {money(receipt.consideration, receipt.currency)}
          <Warning trade={receipt} />
        </div>
      )}
    </form>
  );
}

function TradeRow({ trade, onChange }) {
  const [price, setPrice] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const action = nextStatus[trade.status];
  const executing = trade.status === 'SENT';

  async function advance(event) {
    event.preventDefault();
    setError('');
    const body = { status: action[0] };
    if (executing) {
      if (!positiveDecimal(price.trim())) return setError('Enter a positive executed price.');
      body.executed_price = price.trim();
    }
    setSaving(true);
    try {
      onChange(await request('/trades/' + trade.id + '/status', { method: 'PATCH', body }));
      setPrice('');
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr>
      <td><strong>{trade.instrument_code}</strong><small>#{trade.id} · {trade.fund}</small></td>
      <td><span className={'side ' + trade.side.toLowerCase()}>{trade.side}</span><small>{trade.qty} units</small></td>
      <td>{trade.price}{trade.executed_price != null && <small>Executed {trade.executed_price}</small>}</td>
      <td>{trade.broker}<small>{displayDate(trade.trade_date)}</small></td>
      <td className="amount"><span>{money(trade.consideration, trade.currency)}</span>
        {trade.last_close == null && !trade.warning && <small>Close unavailable</small>}
        <Warning trade={trade} />
      </td>
      <td><span className={'status ' + trade.status.toLowerCase()}>{trade.status}</span>
        {action && (
          <form className="action" onSubmit={advance}>
            {executing && <input required disabled={saving} inputMode="decimal" value={price}
              aria-label={'Executed price for trade ' + trade.id} placeholder="Executed price"
              onChange={event => setPrice(event.target.value)} />}
            <button disabled={saving} type="submit">{saving ? 'Saving…' : action[1]}</button>
            {error && <p className="error" role="alert">{error}</p>}
          </form>
        )}
      </td>
    </tr>
  );
}

function useResource(load, dependencies) {
  const [result, setResult] = useState({ loading: true });
  useEffect(() => {
    const controller = new AbortController();
    setResult({ loading: true });
    load(controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ data });
    }).catch(error => {
      if (!controller.signal.aborted) setResult({ error: error.message });
    });
    return () => controller.abort();
  }, dependencies);
  return [result, setResult];
}

function App() {
  const [today, setToday] = useState(southAfricanToday);
  const [fund, setFund] = useState('');
  const [catalogVersion, setCatalogVersion] = useState(0);
  const [ledgerVersion, setLedgerVersion] = useState(0);
  const query = new URLSearchParams({ date: today });
  if (fund) query.set('fund', fund);
  const [catalog] = useResource(signal => Promise.all([
    request('/reference-data', { signal }),
    request('/instruments', { signal }),
  ]), [catalogVersion]);
  const [ledger, setLedger] = useResource(
    signal => request('/trades?' + query, { signal }),
    [today, fund, ledgerVersion],
  );

  useEffect(() => {
    const timer = setInterval(() => setToday(southAfricanToday()), 1000);
    return () => clearInterval(timer);
  }, []);

  const reload = () => setLedgerVersion(version => version + 1);
  const updateTrade = trade => setLedger(current => current.data
    ? { data: current.data.map(row => row.id === trade.id ? trade : row) }
    : current);

  return (
    <>
      <header className="topbar">
        <div className="brand"><span className="monogram" aria-hidden="true">C</span> Corion Capital</div>
        <div className="session">{displayDate(today)} <span>SAST</span></div>
      </header>
      <main>
        <h1>Trade Ledger</h1>
        <div className="desk">
          <section className="panel capture" aria-labelledby="capture-heading">
            <div className="panel-head"><h2 id="capture-heading">Capture trade</h2></div>
            <div className="panel-body">
              {catalog.loading && <p role="status">Loading trading reference data…</p>}
              {catalog.error && <>
                <p className="error" role="alert">{catalog.error}</p>
                <button onClick={() => setCatalogVersion(version => version + 1)}>Retry</button>
              </>}
              {catalog.data && (catalog.data[1].length && catalog.data[0].funds.length && catalog.data[0].brokers.length
                ? <Capture reference={catalog.data[0]} instruments={catalog.data[1]} today={today} onChange={reload} />
                : <p>No trading reference data available.</p>)}
            </div>
          </section>
          <section className="panel ledger" aria-labelledby="ledger-heading">
            <div className="panel-head ledger-head">
              <div><h2 id="ledger-heading">Today’s trades</h2><p>{displayDate(today)}</p></div>
              <label className="filter">
                <span id="fund-filter-label">Fund filter</span>
                <select aria-labelledby="fund-filter-label" value={fund} onChange={event => setFund(event.target.value)}>
                  <option value="">All funds</option>
                  {catalog.data?.[0].funds.map(item => <option key={item}>{item}</option>)}
                </select>
              </label>
            </div>
            {ledger.loading && <p className="ledger-state" role="status">Loading trades…</p>}
            {ledger.error && <div className="ledger-state">
              <p className="error" role="alert">{ledger.error}</p><button onClick={reload}>Retry</button>
            </div>}
            {ledger.data?.length === 0 && <p className="ledger-state" role="status">
              {fund ? 'No trades for ' + fund + ' today.' : 'No trades captured today.'}
            </p>}
            {Boolean(ledger.data?.length) && (
              <div className="table-scroll" tabIndex="0" aria-label="Today’s trade ledger" role="region">
                <table>
                  <thead><tr>
                    {['Instrument', 'Side / qty', 'Price', 'Broker', 'Consideration', 'Status'].map(label =>
                      <th scope="col" key={label}>{label}</th>)}
                  </tr></thead>
                  <tbody>{ledger.data.map(trade => <TradeRow trade={trade} key={trade.id} onChange={updateTrade} />)}</tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </main>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
