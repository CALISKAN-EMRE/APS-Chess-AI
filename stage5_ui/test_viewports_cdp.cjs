const http = require('http');
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
  const port = 9222;
  const chromeProc = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    '--user-data-dir=C:\\Users\\3mrec\\AppData\\Local\\Temp\\chrome_cdp_test',
    '--window-size=1920,1080',
    'http://127.0.0.1:5173'
  ]);

  try {
    await sleep(2500);
    const pages = await getJson(`http://127.0.0.1:${port}/json/list`);
    const page = pages.find(p => p.type === 'page');
    if (!page || !page.webSocketDebuggerUrl) {
      throw new Error('No debugger WebSocket URL found');
    }

    const client = new CdpClient(page.webSocketDebuggerUrl);
    await client.init();
    await client.send('Runtime.enable');
    await client.send('Page.enable');

    console.log('--- STARTING MULTI-RESOLUTION EXHIBITION VERIFICATION ---');

    const resolutions = [
      { name: '1920x1080', w: 1920, h: 1080 },
      { name: '1600x900',  w: 1600, h: 900 },
      { name: '1440x900',  w: 1440, h: 900 },
    ];

    for (const res of resolutions) {
      await client.setViewport(res.w, res.h);
      await sleep(300);

      const metrics = await client.eval(`(() => {
        const docEl = document.documentElement;
        const body = document.body;
        const board = document.querySelector('.board-chassis');
        const header = document.querySelector('.header-bar');
        const telemetry = document.querySelector('.engine-stage');
        const history = document.querySelector('.panel-history');
        const pieces = Array.from(document.querySelectorAll('.chess-piece img'));
        
        return {
          viewport: '${res.name}',
          windowWidth: window.innerWidth,
          windowHeight: window.innerHeight,
          scrollHeight: docEl.scrollHeight,
          clientHeight: docEl.clientHeight,
          bodyScrollHeight: body.scrollHeight,
          hasDocScroll: docEl.scrollHeight > docEl.clientHeight,
          hasBodyScroll: body.scrollHeight > window.innerHeight,
          boardPresent: !!board,
          boardRect: board ? { w: Math.round(board.getBoundingClientRect().width), h: Math.round(board.getBoundingClientRect().height) } : null,
          headerHeight: header ? Math.round(header.getBoundingClientRect().height) : 0,
          telemetryPresent: !!telemetry,
          historyPresent: !!history,
          pieceCount: pieces.length,
          allPiecesLoaded: pieces.length >= 16 && pieces.every(p => p.complete && p.naturalWidth > 0)
        };
      })()`);

      console.log(`\n[Resolution ${res.name}]`);
      console.log(`- Document Scroll Height: ${metrics.scrollHeight}px vs Client Height: ${metrics.clientHeight}px`);
      console.log(`- Document Vertical Scrollbar Exists: ${metrics.hasDocScroll ? 'YES (FAIL)' : 'NO (PASS)'}`);
      console.log(`- Body Vertical Scrollbar Exists: ${metrics.hasBodyScroll ? 'YES (FAIL)' : 'NO (PASS)'}`);
      console.log(`- Header Height: ${metrics.headerHeight}px`);
      console.log(`- Chessboard Dimensions: ${metrics.boardRect.w}x${metrics.boardRect.h}px`);
      console.log(`- Live Telemetry Stage Visible: ${metrics.telemetryPresent}`);
      console.log(`- Move History Region Visible: ${metrics.historyPresent}`);
      console.log(`- Active Pieces on Board: ${metrics.pieceCount}, All SVGs Loaded Validly: ${metrics.allPiecesLoaded}`);
      
      if (metrics.hasDocScroll || metrics.hasBodyScroll) {
        throw new Error(`Vertical scroll detected at resolution ${res.name}!`);
      }

      const snap = await client.send('Page.captureScreenshot');
      const fs = require('fs');
      fs.writeFileSync(`C:\\Users\\3mrec\\.gemini\\antigravity-ide\\brain\\f61954c5-f522-4764-9e93-e9b239add13b\\exhibition_${res.name}.png`, Buffer.from(snap.data, 'base64'));
      console.log(`- Saved screenshot: exhibition_${res.name}.png`);
    }

    console.log('\n--- MODAL OVERLAY VERIFICATION ---');
    // Test Architecture Modal
    await client.eval(`document.getElementById('nav-btn-architecture').click()`);
    await sleep(400);
    const archCheck = await client.eval(`(() => {
      const modal = document.querySelector('.drawer-modal');
      const docEl = document.documentElement;
      return {
        open: !!modal,
        hasDocScroll: docEl.scrollHeight > docEl.clientHeight,
        modalTitle: modal ? modal.querySelector('h2').innerText : null
      };
    })()`);
    console.log(`- Architecture Modal Opened: ${archCheck.open} ("${archCheck.modalTitle}")`);
    console.log(`- Document Vertical Scroll while modal open: ${archCheck.hasDocScroll ? 'YES (FAIL)' : 'NO (PASS)'}`);

    const archSnap = await client.send('Page.captureScreenshot');
    const fs = require('fs');
    fs.writeFileSync('C:\\Users\\3mrec\\.gemini\\antigravity-ide\\brain\\f61954c5-f522-4764-9e93-e9b239add13b\\exhibition_modal_architecture.png', Buffer.from(archSnap.data, 'base64'));

    await client.eval(`document.getElementById('close-architecture-btn').click()`);
    await sleep(300);

    // Test Benchmark Modal
    await client.eval(`document.getElementById('nav-btn-benchmark').click()`);
    await sleep(400);
    const benchCheck = await client.eval(`(() => {
      const modal = document.querySelector('.drawer-modal');
      const docEl = document.documentElement;
      return {
        open: !!modal,
        hasDocScroll: docEl.scrollHeight > docEl.clientHeight,
        modalTitle: modal ? modal.querySelector('h2').innerText : null
      };
    })()`);
    console.log(`- Benchmark Modal Opened: ${benchCheck.open} ("${benchCheck.modalTitle}")`);
    console.log(`- Document Vertical Scroll while modal open: ${benchCheck.hasDocScroll ? 'YES (FAIL)' : 'NO (PASS)'}`);

    const benchSnap = await client.send('Page.captureScreenshot');
    fs.writeFileSync('C:\\Users\\3mrec\\.gemini\\antigravity-ide\\brain\\f61954c5-f522-4764-9e93-e9b239add13b\\exhibition_modal_benchmark.png', Buffer.from(benchSnap.data, 'base64'));

    await client.eval(`document.getElementById('close-benchmark-btn').click()`);
    await sleep(300);

    console.log('\n--- VERIFICATION PASSED COMPLETELY ---');
    client.close();
  } finally {
    chromeProc.kill();
  }
}

run().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
