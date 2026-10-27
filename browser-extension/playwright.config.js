// Playwright config for Parvan Browser Extension tests
const config = {
  testDir: './tests',
  timeout: 30000,
  reporter: 'html',
  use: {
    headless: true,
    launchOptions: {
      args: [
        '--disable-extensions-except=.',
        '--load-extension=.',
      ],
    },
  },
  projects: [
    {
      name: 'msedge',
      use: {
        channel: 'msedge',
      },
    },
  ],
};

module.exports = config;
