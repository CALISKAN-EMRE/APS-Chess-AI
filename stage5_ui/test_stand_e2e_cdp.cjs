const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

function getJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.msgId = 1;
    this.callbacks = new Map();
  }

  init() {
    return new Promise((resolve, reject) => {
      this.ws.onopen = resolve;
      this.ws.onerror = reject;
      this.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.id && this.callbacks.has(data.id)) {
          const cb = this.callbacks.get(data.id);
          this.callbacks.delete(data.id);
          if (data.error) cb.reject(data.error);
          else cb.resolve(data.result);
        }
      };
    });
  }

  send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.msgId++;
      this.callbacks.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error('Eval failed: ' + JSON.stringify(res.exceptionDetails));
    }
    return res.result ? res.result.value : undefined;
  }

  async setViewport(width, height) {
    await this.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
  }

  close() {
    this.ws.close();
  }
}

async function run() {
  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const port = 9224;
  const artifactDir = 'C:\\Users\\3mrec\\.gemini\\antigravity-ide\\brain\\f61954c5-f522-4764-9e93-e9b239add13b';

  console.log('Spawning Chrome for Final Stand Product Verification...');
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    '--user-data-dir=C:\\Users\\3mrec\\AppData\\Local\\Temp\\chrome_cdp_stand',
    '--window-size=1920,1080',
    'http://127.0.0.1:5173'
  ]);

  try {
    await sleep(3000);
    const pages = await getJson(`http://127.0.0.1:${port}/json/list`);
    const page = pages.find(p => p.type === 'page');
    if (!page || !page.webSocketDebuggerUrl) {
      throw new Error('No debugger WebSocket URL found');
    }

    const client = new CdpClient(page.webSocketDebuggerUrl);
    await client.init();
    await client.send('Runtime.enable');
    await client.send('Page.enable');

    console.log('=== CHECK 1: Viewport & Layout (Zero Body Scroll at 1920x1080 and 1600x900) ===');
    await client.setViewport(1920, 1080);
    await sleep(600);

    const vp1080 = await client.eval(`(() => {
      const docEl = document.documentElement;
      const body = document.body;
      return {
        hasDocScroll: docEl.scrollHeight > docEl.clientHeight,
        hasBodyScroll: body.scrollHeight > window.innerHeight,
        docScrollHeight: docEl.scrollHeight,
        clientHeight: docEl.clientHeight,
      };
    })()`);
    console.log('  1920x1080 scroll check:', vp1080);
    if (vp1080.hasDocScroll || vp1080.hasBodyScroll) {
      throw new Error('Scroll detected at 1920x1080');
    }

    await client.setViewport(1600, 900);
    await sleep(600);
    const vp900 = await client.eval(`(() => {
      const docEl = document.documentElement;
      const body = document.body;
      return {
        hasDocScroll: docEl.scrollHeight > docEl.clientHeight,
        hasBodyScroll: body.scrollHeight > window.innerHeight,
        docScrollHeight: docEl.scrollHeight,
        clientHeight: docEl.clientHeight,
      };
    })()`);
    console.log('  1600x900 scroll check:', vp900);
    if (vp900.hasDocScroll || vp900.hasBodyScroll) {
      throw new Error('Scroll detected at 1600x900');
    }

    await client.setViewport(1920, 1080);
    await sleep(300);

    console.log('\n=== CHECK 2: Absence of Dev/Stage Terminology & Clean Header ===');
    const headerCheck = await client.eval(`(() => {
      const bodyText = document.body.innerText;
      const hasStage5 = bodyText.includes('STAGE 5') || bodyText.includes('Stage 5');
      const hasStage4 = bodyText.includes('STAGE 4') || bodyText.includes('Stage 4');
      const hasTTPVS = bodyText.includes('TT+PVS');
      const archBtn = document.getElementById('nav-btn-architecture');
      const benchBtn = document.getElementById('nav-btn-benchmark');
      const statusPill = document.getElementById('header-status-pill');
      return {
        hasStage5,
        hasStage4,
        hasTTPVS,
        archBtnPresent: !!archBtn,
        benchBtnPresent: !!benchBtn,
        statusPillText: statusPill ? statusPill.innerText.trim() : null
      };
    })()`);
    console.log('  Header & Text audit:', headerCheck);
    if (headerCheck.hasStage5 || headerCheck.hasStage4 || headerCheck.hasTTPVS) {
      throw new Error('Dev/Stage labels found in UI: ' + JSON.stringify(headerCheck));
    }
    if (headerCheck.archBtnPresent || headerCheck.benchBtnPresent) {
      throw new Error('Architecture or Benchmark buttons still visible in header!');
    }
    console.log('  -> PASSED: No dev tags, no Architecture/Benchmark buttons.');

    console.log('\n=== CHECK 3: Time Control Recommendations ===');
    await client.eval(`document.getElementById('btn-time-3m').click()`);
    await sleep(150);
    const rec3 = await client.eval(`document.getElementById('time-control-recommendation').innerText`);
    console.log('  3m recommendation text:', rec3);
    if (!rec3.includes('D1 Fast recommended')) {
      throw new Error('Expected "D1 Fast recommended" in: ' + rec3);
    }

    await client.eval(`document.getElementById('btn-time-5m').click()`);
    await sleep(150);
    const rec5 = await client.eval(`document.getElementById('time-control-recommendation').innerText`);
    console.log('  5m recommendation text:', rec5);
    if (!rec5.includes('D2 recommended')) {
      throw new Error('Expected "D2 recommended" in: ' + rec5);
    }
    console.log('  -> PASSED: Subtle recommendations verified.');

    console.log('\n=== CHECK 4: Starting a 3-minute Game as White (Default Setup) ===');
    // Configure settings: White, 3 MIN, D2
    await client.eval(`document.getElementById('btn-time-3m').click()`);
    await sleep(100);
    await client.eval(`document.getElementById('btn-choose-white').click()`);
    await sleep(100);
    await client.eval(`document.getElementById('btn-depth-2').click()`);
    await sleep(200);
    await client.eval(`document.getElementById('btn-restart').click()`);
    await sleep(600);

    const initialClocks = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      const readyBadge = document.getElementById('status-game-ready');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
        whiteActive: w?.classList.contains('clock-active'),
        blackActive: b?.classList.contains('clock-active'),
        readyText: readyBadge?.innerText.trim()
      };
    })()`);
    console.log('  Initial clock state:', initialClocks);
    if (initialClocks.whiteText !== '3:00' || initialClocks.blackText !== '3:00') {
      throw new Error('Clocks do not start at exactly 3:00 / 3:00: ' + JSON.stringify(initialClocks));
    }
    if (initialClocks.whiteActive || initialClocks.blackActive) {
      throw new Error('Clocks should be paused before move 1: ' + JSON.stringify(initialClocks));
    }
    if (!initialClocks.readyText.includes('GAME READY · WHITE TO MOVE')) {
      throw new Error('Expected "GAME READY · WHITE TO MOVE", got: ' + initialClocks.readyText);
    }
    console.log('  -> PASSED: Clocks paused at 3:00 / 3:00 and GAME READY · WHITE TO MOVE displayed.');

    // Screenshot of Game Ready
    const shot1 = await client.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'stand_game_ready_1080p.png'), Buffer.from(shot1.data, 'base64'));

    // Wait 2s to ensure no clock ticks while paused
    console.log('  Waiting 2s to verify clock remains frozen...');
    await sleep(2000);
    const clocksAfterPause = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
      };
    })()`);
    console.log('  Clocks after 2s pause:', clocksAfterPause);
    if (clocksAfterPause.whiteText !== '3:00' || clocksAfterPause.blackText !== '3:00') {
      throw new Error('Clocks ticked during game-not-started state!');
    }
    console.log('  -> PASSED: Clocks are completely frozen.');

    // Test F5 refresh before move 1
    console.log('\n=== CHECK 5: F5 Refresh before move 1 ===');
    await client.send('Page.reload');
    await sleep(2000);
    const clocksAfterF5 = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      const readyBadge = document.getElementById('status-game-ready');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
        whiteActive: w?.classList.contains('clock-active'),
        blackActive: b?.classList.contains('clock-active'),
        readyText: readyBadge?.innerText.trim()
      };
    })()`);
    console.log('  Clocks after F5:', clocksAfterF5);
    if (clocksAfterF5.whiteText !== '3:00' || clocksAfterF5.blackText !== '3:00') {
      throw new Error('Clocks not 3:00 after F5!');
    }
    if (clocksAfterF5.whiteActive || clocksAfterF5.blackActive) {
      throw new Error('Clocks became active after F5!');
    }
    console.log('  -> PASSED: F5 preserved unstarted state.');

    // White plays 1. e4
    console.log('\n=== CHECK 6: White first move and clock activation ===');
    await client.eval(`(() => {
      document.getElementById('sq-e2').click();
    })()`);
    await sleep(200);
    await client.eval(`(() => {
      document.getElementById('sq-e4').click();
    })()`);
    await sleep(500);

    const clocksAfterMove1 = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
        whiteActive: w?.classList.contains('clock-active'),
        blackActive: b?.classList.contains('clock-active'),
      };
    })()`);
    console.log('  Clocks immediately after White 1. e4:', clocksAfterMove1);
    if (clocksAfterMove1.whiteText !== '3:00') {
      throw new Error('White move 1 consumed time! ' + JSON.stringify(clocksAfterMove1));
    }
    if (!clocksAfterMove1.blackActive) {
      throw new Error("Black's clock should be active after White move 1!");
    }
    console.log('  -> PASSED: White move 1 consumed 0s, Black clock is now active.');

    // Wait for AI move as Black (triggered automatically by handleMakeMove)
    console.log('  Waiting for AI response for Black...');
    await sleep(4500);

    const clocksAfterAIMove = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
        whiteActive: w?.classList.contains('clock-active'),
        blackActive: b?.classList.contains('clock-active'),
      };
    })()`);
    console.log('  Clocks after Black AI move:', clocksAfterAIMove);
    if (clocksAfterAIMove.blackText === '3:00') {
      throw new Error('Black AI move did not consume clock time!');
    }
    if (!clocksAfterAIMove.whiteActive) {
      throw new Error("White clock should be active after Black's move!");
    }
    console.log('  -> PASSED: Black AI consumed time, White clock is now active.');

    console.log('\n=== CHECK 7: Game-Start Clock Semantics (Human as Black) ===');
    await client.eval(`document.getElementById('btn-time-3m').click()`);
    await sleep(100);
    await client.eval(`document.getElementById('btn-choose-black').click()`);
    await sleep(100);
    await client.eval(`document.getElementById('btn-depth-1').click()`);
    await sleep(200);
    await client.eval(`document.getElementById('btn-restart').click()`);
    // AI moves first
    await sleep(4000);

    const blackGameClocks = await client.eval(`(() => {
      const w = document.getElementById('clock-white');
      const b = document.getElementById('clock-black');
      return {
        whiteText: w?.innerText.trim(),
        blackText: b?.innerText.trim(),
        whiteActive: w?.classList.contains('clock-active'),
        blackActive: b?.classList.contains('clock-active'),
      };
    })()`);
    console.log('  Clocks after AI opening move for Black game:', blackGameClocks);
    if (blackGameClocks.whiteText !== '3:00') {
      throw new Error('AI opening move consumed time for White! ' + JSON.stringify(blackGameClocks));
    }
    if (!blackGameClocks.blackActive) {
      throw new Error("Black's clock should be active after AI opening move!");
    }
    console.log('  -> PASSED: AI opening move consumed 0s, Black clock active.');

    // Switch to 1600x900 and take screenshot
    await client.setViewport(1600, 900);
    await sleep(600);
    const shot2 = await client.send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(artifactDir, 'stand_game_play_900p.png'), Buffer.from(shot2.data, 'base64'));
    console.log('Saved 1600x900 screenshot.');

    console.log('\n=== ALL VERIFICATION CHECKS PASSED PERFECTLY! ===');
  } finally {
    chromeProc.kill();
  }
}

run().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
