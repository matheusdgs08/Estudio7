const http = require('http');
const fs = require('fs');
const path = require('path');
const PORT = process.env.PORT || 3000;

const ROUTES = {
  '/': 'index.html',
  '/professor': 'index.html',
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

http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  // Static JS/CSS files
  const ext = path.extname(url);
  if (ext && MIME[ext]) {
    const filePath = path.join(__dirname, url.slice(1));
    fs.readFile(filePath, (err, data) => {
      if (err) { res.writeHead(404); res.end('Not found'); return; }
      res.writeHead(200, { 'Content-Type': MIME[ext], 'Cache-Control': 'public, max-age=300' });
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
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
  });
}).listen(PORT, () => console.log(`Estudio7 na porta ${PORT}`));
