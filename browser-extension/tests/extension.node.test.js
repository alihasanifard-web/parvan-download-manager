const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const baseDir = path.join(__dirname, '..');

test('Parvan Extension - manifest.json structure and validity', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(baseDir, 'manifest.json'), 'utf8'));
  assert.strictEqual(manifest.manifest_version, 3);
  assert.ok(manifest.name.includes('پروان'));
  assert.strictEqual(manifest.version, '3.0.0');
  assert.strictEqual(manifest.background.service_worker, 'background.js');
  assert.ok(manifest.permissions.includes('downloads'));
  assert.ok(manifest.permissions.includes('contextMenus'));
  assert.ok(manifest.icons['16'] && manifest.icons['32'] && manifest.icons['48'] && manifest.icons['128']);
});

test('Parvan Extension - background.js communication & endpoints', () => {
  const content = fs.readFileSync(path.join(baseDir, 'background.js'), 'utf8');
  assert.ok(content.includes('sendToParvan'));
  assert.ok(content.includes('chrome.runtime.onInstalled'));
  assert.ok(content.includes('chrome.contextMenus.create'));
  assert.ok(content.includes('127.0.0.1:9876'));
});

test('Parvan Extension - content.js video sniffer logic', () => {
  const content = fs.readFileSync(path.join(baseDir, 'content.js'), 'utf8');
  assert.ok(content.includes('createFloatingButton'));
  assert.ok(content.includes('scanVideos'));
  assert.ok(content.includes('parvan-video-grabber-btn'));
});

test('Parvan Extension - popup files consistency', () => {
  assert.ok(fs.existsSync(path.join(baseDir, 'popup.html')));
  assert.ok(fs.existsSync(path.join(baseDir, 'popup.js')));
  assert.ok(fs.existsSync(path.join(baseDir, 'popup.css')));
  const html = fs.readFileSync(path.join(baseDir, 'popup.html'), 'utf8');
  assert.ok(html.includes('metricSpeed'));
  assert.ok(html.includes('inputUrl'));
});
