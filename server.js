const http = require('http');
const fs = require('fs');
const path = require('path');
const PORT = process.env.PORT || 3000;

const ROUTES = {
  '/': 'index.html',
  '/professor': 'index.html',
  '/vanessa': 'vanessa.html',
  '/coordenacao': 'vanessa.html',
};

http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  const file = ROUTES[url] || (url.endsWith('.html') ? url.slice(1) : null);
  if (!file) { res.writeHead(302, { Location: '/' }); res.end(); return; }
  const filePath = path.join(__dirname, file);
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(data);
  });
}).listen(PORT, () => console.log(`Estudio7 na porta ${PORT}`));
