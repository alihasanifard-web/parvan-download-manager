// Parvan Browser Extension - Playwright Test Suite
// Tests background.js, content.js, popup.js, manifest.json

const { test, expect } = require('@playwright/test');

test.describe('Parvan Extension Manifest', () => {
  test('manifest.json exists and is valid JSON', async () => {
    const manifestPath = require('path').join(__dirname, '..', 'manifest.json');
    const fs = require('fs');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.name).toContain('پروان');
    expect(manifest.version).toBe('3.0.0');
    expect(manifest.background.service_worker).toBe('background.js');
    expect(manifest.content_scripts[0].js[0]).toBe('content.js');
    expect(manifest.permissions).toContain('downloads');
    expect(manifest.permissions).toContain('contextMenus');
    expect(manifest.host_permissions.some(p => p.includes('127.0.0.1:9876'))).toBe(true);
  });

  test('manifest has all required icon sizes', async () => {
    const manifestPath = require('path').join(__dirname, '..', 'manifest.json');
    const fs = require('fs');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    
    expect(manifest.icons).toHaveProperty('16');
    expect(manifest.icons).toHaveProperty('32');
    expect(manifest.icons).toHaveProperty('48');
    expect(manifest.icons).toHaveProperty('128');
  });
});

test.describe('Parvan Background Script Logic', () => {
  test('background.js has sendToParvan function', async () => {
    const fs = require('fs');
    const bg = fs.readFileSync(require('path').join(__dirname, '..', 'background.js'), 'utf8');
    
    expect(bg).toContain('async function sendToParvan');
    expect(bg).toContain('chrome.runtime.onInstalled');
    expect(bg).toContain('chrome.contextMenus.create');
    expect(bg).toContain('chrome.downloads.onCreated');
    expect(bg).toContain('chrome.runtime.onMessage');
    expect(bg).toContain('http://127.0.0.1:9876/api');
  });

  test('content.js has video sniffer and floating button', async () => {
    const fs = require('fs');
    const content = fs.readFileSync(require('path').join(__dirname, '..', 'content.js'), 'utf8');
    
    expect(content).toContain('createFloatingButton');
    expect(content).toContain('scanVideos');
    expect(content).toContain('chrome.runtime.sendMessage');
    expect(content).toContain('download_media');
    expect(content).toContain('parvan-video-grabber-btn');
  });

  test('popup.js has API integration and UI controls', async () => {
    const fs = require('fs');
    const popup = fs.readFileSync(require('path').join(__dirname, '..', 'popup.js'), 'utf8');
    
    expect(popup).toContain('http://127.0.0.1:9876/api');
    expect(popup).toContain('checkStatus');
    expect(popup).toContain('setInterval');
    expect(popup).toContain('autoIntercept');
    expect(popup).toContain('threads');
  });
});

test.describe('Parvan Extension Integration', () => {
  test('popup.html loads and contains required elements', async () => {
    const fs = require('fs');
    const popupHtml = fs.readFileSync(require('path').join(__dirname, '..', 'popup.html'), 'utf8');
    
    expect(popupHtml).toContain('popup.js');
    expect(popupHtml).toContain('popup.css');
    expect(popupHtml).toContain('statusBadge');
    expect(popupHtml).toContain('metricSpeed');
    expect(popupHtml).toContain('metricActive');
    expect(popupHtml).toContain('inputUrl');
    expect(popupHtml).toContain('btnDownload');
  });

  test('all extension files exist', async () => {
    const fs = require('fs');
    const extDir = require('path').join(__dirname, '..');
    const requiredFiles = [
      'manifest.json',
      'background.js',
      'content.js',
      'popup.js',
      'popup.html',
      'popup.css',
    ];
    
    for (const file of requiredFiles) {
      expect(fs.existsSync(require('path').join(extDir, file))).toBe(true);
    }
  });
});
