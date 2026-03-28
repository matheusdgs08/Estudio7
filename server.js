const http = require('http');
const fs = require('fs');
const path = require('path');
const PORT = process.env.PORT || 3000;

const ROUTES = {
  '/': 'index.html',
  '/colaborador': 'colaborador.html',
  '/impressao': 'impressao.html',
  '/vanessa': 'vanessa.html',
  '/coordenacao': 'vanessa.html',
  '/agendar': 'agendar.html',
  '/login':    'login.html',
  '/recepcao': 'recepcao.html',
  '/impressao/servico/download': 'servico_impressao/impressora.py',
  '/questionario': 'questionario.html',
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css',
  '.json': 'application/json',
  '.py': 'text/plain; charset=utf-8',
};

const SECURITY_HEADERS = {
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'X-XSS-Protection': '1; mode=block',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy': "default-src 'self' https:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' https: data: blob:; connect-src 'self' https://*.supabase.co https://*.up.railway.app https://api.anthropic.com https://viacep.com.br",
};

http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  // Static JS/CSS files
  const ext = path.extname(url);
  if (ext && MIME[ext]) {
    const filePath = path.join(__dirname, url.slice(1));
    fs.readFile(filePath, (err, data) => {
      if (err) { res.writeHead(404); res.end('Not found'); return; }
      res.writeHead(200, { 'Content-Type': MIME[ext], 'Cache-Control': 'public, max-age=300', ...SECURITY_HEADERS });
      res.end(data);
    });
    return;
  }
  // HTML routes
  const file = ROUTES[url] || (url.endsWith('.html') ? url.slice(1) : null);
  if (!file) { res.writeHead(302, { Location: '/' }); res.end(); return; }
  const filePath = path.join(__dirname, file);
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', ...SECURITY_HEADERS });
    res.end(data);
  });
}).listen(PORT, () => console.log(`Estudio7 na porta ${PORT}`));
