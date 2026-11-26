const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage();
    const base = process.env.FRONTEND_URL || 'http://localhost:5173';
    const api = process.env.API_URL || 'http://localhost:8000/api';
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let releaseLedger;
    const ledgerGate = new Promise(resolve => { releaseLedger = resolve; });
    await page.route('**/api/trades?*', async route => {
      await ledgerGate;
      await route.continue();
    }, { times: 1 });
    await page.goto(base);
    try {
      await page.getByRole('status').filter({ hasText: 'Loading trades' }).waitFor();
    } finally {
      releaseLedger();
    }
    const capture = page.getByRole('region', { name: 'Capture trade' });
    const side = capture.getByLabel('Side');
    const broker = capture.getByLabel('Broker');
    const instrument = capture.getByLabel('Instrument');
    const submit = capture.getByRole('button', { name: 'Capture draft' });
    await submit.waitFor();
    assert.equal(await side.inputValue(), '');
    assert.equal(await broker.inputValue(), '');
    const date = await capture.getByLabel('Trade date').inputValue();
    assert.match(date, /^\d{2}\/\d{2}\/\d{4}$/);
    const iso = date.split('/').reverse().join('-');
    const catalog = await page.request.get(api + '/instruments');
    assert.equal(catalog.status(), 200);
    const mzt = (await catalog.json()).find(item => item.code === 'MZT');
    assert.equal(mzt.quote_unit, 'ZAc');

    const filter = page.getByLabel('Fund filter');
    await filter.selectOption('KESCON');
    await capture.getByLabel('Fund', { exact: true }).selectOption('KESCON');
    await instrument.selectOption(String(mzt.id));
    await side.selectOption('BUY');
    await broker.selectOption('Kudu Securities');
    await capture.getByLabel('Quantity').fill('100');
    await capture.getByLabel('Price (ZAc)', { exact: true }).fill('2500');

    const tradePost = response => response.url().endsWith('/api/trades') &&
      response.request().method() === 'POST';
    for (const detail of ['Test error detail', [{ loc: ['body', 'price'], msg: 'Test price detail' }]]) {
      await page.route('**/api/trades', route => route.fulfill({
        status: 422, json: { detail },
      }), { times: 1 });
      await submit.click();
      await capture.getByRole('alert').filter({
        hasText: Array.isArray(detail) ? 'price: Test price detail' : detail,
      }).waitFor();
    }

    const [response] = await Promise.all([page.waitForResponse(tradePost), submit.click()]);
    assert.equal(response.status(), 201);
    assert.equal(response.request().postDataJSON().trade_date, iso);
    const saved = await response.json();
    assert.equal(saved.consideration, '2500.00');
    assert.equal(saved.status, 'DRAFT');
    const row = page.getByRole('row').filter({ hasText: new RegExp('#' + saved.id + ' ·') });
    await row.getByText('ZAR 2,500.00', { exact: true }).waitFor();
    await row.getByText('DRAFT', { exact: true }).waitFor();
    assert.equal(await side.inputValue(), '');
    assert.equal(await broker.inputValue(), '');
    const query = new URLSearchParams({ fund: 'KESCON', date: iso });
    const ledger = await page.request.get(api + '/trades?' + query);
    assert.equal(ledger.status(), 200);
    assert.ok((await ledger.json()).some(trade => trade.id === saved.id));

    await filter.selectOption('PROINC');
    await page.getByText('No trades for PROINC today.').waitFor();
    assert.equal(await row.count(), 0);
    await page.reload();
    await row.getByText('DRAFT', { exact: true }).waitFor();

    if (process.env.CHECK_P1 === '1') {
      await row.getByRole('button', { name: 'Mark sent' }).click();
      await row.getByText('SENT', { exact: true }).waitFor();
      await row.getByLabel(/Executed price for trade/).fill('2550');
      await row.getByRole('button', { name: 'Execute' }).click();
      await row.getByText('EXECUTED', { exact: true }).waitFor();
      await row.getByText('ZAR 2,550.00', { exact: true }).waitFor();
      await row.getByRole('button', { name: 'Mark done' }).click();
      await row.getByText('DONE', { exact: true }).waitFor();
    }

    // Use the live catalog and alter one response to exercise the missing-close state.
    await page.route('**/api/instruments', async route => {
      const actual = await route.fetch();
      const instruments = await actual.json();
      const selected = instruments.find(item => item.id === mzt.id);
      selected.last_close = null;
      selected.last_close_date = null;
      await route.fulfill({ response: actual, json: instruments });
    }, { times: 1 });
    await page.reload();
    await instrument.selectOption(String(mzt.id));
    await capture.getByText('Latest close unavailable', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS browser capture, API lookup, fund filter, reload, loading, errors and missing close');
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
