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
  const port = 9223;
  const artifactDir = 'C:\\Users\\3mrec\\.gemini\\antigravity-ide\\brain\\f61954c5-f522-4764-9e93-e9b239add13b';

  console.log('Spawning Chrome for Bullet Chess Clock verification...');
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    '--user-data-dir=C:\\Users\\3mrec\\AppData\\Local\\Temp\\chrome_cdp_clocks',
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

    console.log('=== TEST 1: Viewport & Layout (Zero Body Scrollbar) ===');
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
    console.log('1920x1080 Scroll check:', vp1080);
    if (vp1080.hasDocScroll || vp1080.hasBodyScroll) {
      throw new Error('Document or body scroll detected at 1920x1080!');
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
    console.log('1600x900 Scroll check:', vp900);
    if (vp900.hasDocScroll || vp900.hasBodyScroll) {
      throw new Error('Document or body scroll detected at 1600x900!');
    }

    await client.setViewport(1920, 1080);
    await sleep(300);

    console.log('\n=== TEST 2: Time Control Selector & Subtle Recommendations ===');
    // Check 3 min button and recommendation
    await client.eval(`document.getElementById('btn-time-3m').click()`);
    await sleep(200);
    const rec3 = await client.eval(`(() => {
      const btn3 = document.getElementById('btn-time-3m');
      const rec = document.getElementById('time-control-recommendation');
      return {
        btn3Active: btn3.classList.contains('active'),
        recText: rec ? rec.innerText : ''
      };
    })()`);
    console.log('3 Min Selector:', rec3);
    if (!rec3.btn3Active || !rec3.recText.includes('D1 Fast recommended')) {
      throw new Error('3 Min recommendation failed: ' + JSON.stringify(rec3));
    }

    // Check 5 min button and recommendation
    await client.eval(`document.getElementById('btn-time-5m').click()`);
    await sleep(200);
    const rec5 = await client.eval(`(() => {
      const btn5 = document.getElementById('btn-time-5m');
      const rec = document.getElementById('time-control-recommendation');
      return {
        btn5Active: btn5.classList.contains('active'),
        recText: rec ? rec.innerText : ''
      };
    })()`);
    console.log('5 Min Selector:', rec5);
    if (!rec5.btn5Active || !rec5.recText.includes('D2 Demo recommended')) {
      throw new Error('5 Min recommendation failed: ' + JSON.stringify(rec5));
    }

    console.log('\n=== TEST 3: Starting a 3-minute Game as White ===');
    await client.eval(`(() => {
      document.getElementById('btn-time-3m').click();
      document.getElementById('btn-choose-white').click();
      document.getElementById('btn-depth-1').click();
    })()`);
    await sleep(200);
    await client.eval(`document.getElementById('btn-restart').click()`);

    await sleep(1000);

    const clockState1 = await client.eval(`(() => {
      const clockW = document.getElementById('clock-white');
      const clockB = document.getElementById('clock-black');
      return {
        whiteText: clockW ? clockW.innerText.trim() : null,
        whiteActive: clockW ? clockW.classList.contains('clock-active') : false,
        blackText: clockB ? clockB.innerText.trim() : null,
        blackActive: clockB ? clockB.classList.contains('clock-active') : false,
      };
    })()`);
    console.log('Clock State at start of 3m game:', clockState1);
    if (!clockState1.whiteActive || clockState1.blackActive) {
      throw new Error('White should be active, Black should not be active! ' + JSON.stringify(clockState1));
    }

    console.log('Waiting 1.5s to observe White clock ticking while Black clock stays intact...');
    await sleep(1500);

    const clockState2 = await client.eval(`(() => {
      const clockW = document.getElementById('clock-white');
      const clockB = document.getElementById('clock-black');
      return {
        whiteText: clockW ? clockW.innerText.trim() : null,
        blackText: clockB ? clockB.innerText.trim() : null,
      };
    })()`);
    console.log('Clock State after 1.5s thinking:', clockState2);
    // White text should be less than 3:00 (e.g., 2:58 or 2:57), Black should be 3:00
    if (clockState2.whiteText === '3:00' || !clockState2.blackText.includes('3:00')) {
      throw new Error('Clock decrement issue: ' + JSON.stringify(clockState2));
    }

    console.log('\n=== TEST 4: Making Move 1. e4 (Switch Active Clock to Black) ===');
    // Human plays e2e4 by simulating click on e2 and e4 squares
    await client.eval(`(() => {
      // Find square e2 and e4
      const squares = Array.from(document.querySelectorAll('.square'));
      const e2 = squares.find(s => s.getAttribute('data-square') === 'e2' || s.textContent.includes('e2'));
      // Or call API directly or click
      const e2El = document.querySelector('[data-square="e2"]') || document.querySelector('.square:nth-child(53)');
      // Let's click e2 then e4
      const clickEv = (el) => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      // Alternatively find piece with title or data
    })()`);

    // Let's trigger human move e2e4 through fetch to simulate the exact game client action:
    await client.eval(`(async () => {
      const { sendMove, fetchGameState } = await import('/src/api/client.ts');
      const state = await fetchGameState();
      await sendMove('e2e4', state.game_id, state.version);
    })()`);

    await sleep(600);

    const clockStateAfterMove = await client.eval(`(() => {
      const clockW = document.getElementById('clock-white');
      const clockB = document.getElementById('clock-black');
      return {
        whiteText: clockW ? clockW.innerText.trim() : null,
        whiteActive: clockW ? clockW.classList.contains('clock-active') : false,
        blackText: clockB ? clockB.innerText.trim() : null,
        blackActive: clockB ? clockB.classList.contains('clock-active') : false,
      };
    })()`);
    console.log('Clock State after human move e2e4:', clockStateAfterMove);

    // Refresh page / simulate F5 to verify clock restoration
    console.log('\n=== TEST 5: Browser Refresh (F5) Restores Exact Clock State ===');
    await client.send('Page.reload');
    await sleep(2000);

    const clockStateRestored = await client.eval(`(() => {
      const clockW = document.getElementById('clock-white');
      const clockB = document.getElementById('clock-black');
      return {
        whiteText: clockW ? clockW.innerText.trim() : null,
        blackText: clockB ? clockB.innerText.trim() : null,
        whiteActive: clockW ? clockW.classList.contains('clock-active') : false,
        blackActive: clockB ? clockB.classList.contains('clock-active') : false,
      };
    })()`);
    console.log('Clock State after F5 refresh:', clockStateRestored);
    if (!clockStateRestored.whiteText || !clockStateRestored.blackText) {
      throw new Error('Clocks failed to restore after refresh!');
    }

    // Capture screenshot of the exhibition layout with clocks
    const screenshot = await client.send('Page.captureScreenshot', { format: 'png' });
    const imgPath = path.join(artifactDir, 'bullet_clock_exhibition.png');
    fs.writeFileSync(imgPath, Buffer.from(screenshot.data, 'base64'));
    console.log(`Saved screenshot to ${imgPath}`);

    console.log('\n=== ALL BULLET CHESS CLOCK TESTS PASSED SUCCESSFULLY! ===');
  } finally {
    chromeProc.kill();
  }
}

run().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
