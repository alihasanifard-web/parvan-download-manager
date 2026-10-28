// End-to-End Test for Parvan Download Manager Dashboard UI
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const INDEX_HTML = path.resolve(__dirname, '..', '..', 'index.html');

test.describe('Parvan Download Manager - Frontend Dashboard E2E', () => {
  test('index.html exists and is well-formed HTML5', async () => {
    expect(fs.existsSync(INDEX_HTML)).toBe(true);
    const content = fs.readFileSync(INDEX_HTML, 'utf-8');
    expect(content).toContain('<!DOCTYPE html>');
    expect(content).toContain('پروان دانلود منیجر');
  });

  test('All 5 Next-Gen UI Buttons exist in DOM', async () => {
    const content = fs.readFileSync(INDEX_HTML, 'utf-8');
    expect(content).toContain('id="btnSiteGrabber"');
    expect(content).toContain('id="btnZipPreview"');
    expect(content).toContain('id="btnPrivateVault"');
    expect(content).toContain('id="btnQuotaManager"');
    expect(content).toContain('id="floatingDropTarget"');
  });

  test('All Interactive Modals and Video Player elements exist', async () => {
    const content = fs.readFileSync(INDEX_HTML, 'utf-8');
    expect(content).toContain('id="modalSiteGrabber"');
    expect(content).toContain('id="modalZipPreview"');
    expect(content).toContain('id="modalPrivateVault"');
    expect(content).toContain('id="modalQuotaManager"');
    expect(content).toContain('id="modalLivePlayer"');
    expect(content).toContain('id="liveVideoTag"');
  });

  test('Audio feedback synthesizer is configured', async () => {
    const content = fs.readFileSync(INDEX_HTML, 'utf-8');
    expect(content).toContain('AudioContext');
    expect(content).toContain('playBeep');
  });
});
