const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.PORT || '5173', 10);
const BACKEND_PORT = parseInt(process.env.BACKEND_PORT || '8000', 10);
const DIST_DIR = path.resolve(__dirname, 'frontend/dist');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.eot': 'application/vnd.ms-fontobject',
};

if (!fs.existsSync(DIST_DIR)) {
  console.error(`[ERROR] Frontend build directory not found: ${DIST_DIR}`);
  console.error('Please run: cd stage5_ui/frontend && npm run build');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  const urlPath = req.url || '/';

  // 1. Proxy /api requests to FastAPI backend
  if (urlPath.startsWith('/api/') || urlPath === '/api') {
    const proxyReq = http.request(
      {
        hostname: '127.0.0.1',
        port: BACKEND_PORT,
        path: urlPath,
        method: req.method,
        headers: req.headers,
      },
      (proxyRes) => {
        res.writeHead(proxyRes.statusCode || 500, proxyRes.headers);
        proxyRes.pipe(res);
      }
    );

    proxyReq.on('error', (err) => {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Engine backend unreachable', error: err.message }));
    });

    req.pipe(proxyReq);
    return;
  }

  // 2. Static file serving from frontend/dist
  const cleanPath = urlPath.split('?')[0].split('#')[0];
  let filePath = path.join(DIST_DIR, cleanPath);

  // Prevent directory traversal
  if (!filePath.startsWith(DIST_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  // If path is a directory or does not exist, serve index.html (SPA routing fallback)
  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
      'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=31536000, immutable',
    });
    fs.createReadStream(filePath).pipe(res);
  } else {
    const indexPath = path.join(DIST_DIR, 'index.html');
    if (fs.existsSync(indexPath)) {
      res.writeHead(200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache',
      });
      fs.createReadStream(indexPath).pipe(res);
    } else {
      res.writeHead(404, { 'Content-Type': 'text/plain' });
      res.end('Not Found');
    }
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[APS CHESS AI] Production frontend listening at http://127.0.0.1:${PORT}`);
  console.log(`[APS CHESS AI] Proxying /api to backend at http://127.0.0.1:${BACKEND_PORT}`);
});
