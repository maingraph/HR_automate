import { Page } from 'playwright';
import { ScraperConfig } from '../core/types';

class StealthUtilities {
  private config: ScraperConfig;

  constructor(config: ScraperConfig) {
    this.config = config;
  }

  async setupStealthMode(page: Page): Promise<void> {
    // Override navigator properties to appear more human
    await page.addInitScript(() => {
      // Override the navigator.webdriver property
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
      });

      // Override permissions
      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters: any) => (
        parameters.name === 'notifications' ?
          Promise.resolve({ state: Notification.permission } as PermissionStatus) :
          originalQuery(parameters)
      );

      // Add chrome runtime
      (window as any).chrome = {
        runtime: {},
      };
    });
  }

  async simulateMouseMovement(page: Page): Promise<void> {
    if (!this.config.stealth.enableMouseMovements) return;

    try {
      const viewport = page.viewportSize();
      if (!viewport) return;

      // Generate random coordinates
      const x = Math.floor(Math.random() * viewport.width);
      const y = Math.floor(Math.random() * viewport.height);

      // Move mouse to random position
      await page.mouse.move(x, y, {
        steps: Math.floor(Math.random() * 10) + 5, // 5-15 steps
      });

      // Small delay
      await this.randomDelay(100, 300);
    } catch (error) {
      // Silently fail if mouse movement fails
    }
  }

  async humanScroll(page: Page, direction: 'down' | 'up' = 'down'): Promise<void> {
    if (!this.config.stealth.enableRandomScrolling) {
      // Just do a simple scroll
      await page.evaluate((dir) => {
        window.scrollBy(0, dir === 'down' ? 300 : -300);
      }, direction);
      return;
    }

    try {
      // Scroll in chunks with varying amounts
      const scrolls = Math.floor(Math.random() * 3) + 2; // 2-4 scrolls
      
      for (let i = 0; i < scrolls; i++) {
        const scrollAmount = Math.floor(Math.random() * 200) + 100; // 100-300px
        const finalAmount = direction === 'down' ? scrollAmount : -scrollAmount;
        
        await page.evaluate((amount) => {
          window.scrollBy({
            top: amount,
            behavior: 'smooth',
          });
        }, finalAmount);

        // Random delay between scrolls
        await this.randomDelay(200, 500);
      }
    } catch (error) {
      // Silently fail
    }
  }

  async scrollToLoadAll(page: Page): Promise<void> {
    try {
      let previousHeight = 0;
      let currentHeight = await page.evaluate(() => document.body.scrollHeight);
      let attempts = 0;
      const maxAttempts = 10;

      while (previousHeight !== currentHeight && attempts < maxAttempts) {
        previousHeight = currentHeight;

        // Scroll down in human-like manner
        await this.humanScroll(page, 'down');
        
        // Wait for content to load
        await this.randomDelay(1000, 2000);

        // Get new height
        currentHeight = await page.evaluate(() => document.body.scrollHeight);
        attempts++;
      }

      // Scroll back to top
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
      await this.randomDelay(500, 1000);
    } catch (error) {
      // Continue even if scrolling fails
    }
  }

  async randomPageInteraction(page: Page): Promise<void> {
    if (!this.config.stealth.enablePageInteractions) return;

    try {
      const actions = [
        // Move mouse
        async () => await this.simulateMouseMovement(page),
        // Small scroll
        async () => await this.humanScroll(page, Math.random() > 0.5 ? 'down' : 'up'),
        // Hover over element
        async () => {
          const elements = await page.$$('a, button, div');
          if (elements.length > 0) {
            const randomElement = elements[Math.floor(Math.random() * elements.length)];
            await randomElement.hover().catch(() => {});
          }
        },
      ];

      // Pick random action
      const action = actions[Math.floor(Math.random() * actions.length)];
      await action();
    } catch (error) {
      // Silently fail
    }
  }

  async simulateReading(page: Page): Promise<void> {
    // Simulate reading time by doing nothing for a bit
    await this.randomDelay(2000, 5000);
    
    // Maybe scroll a bit while "reading"
    if (Math.random() > 0.5) {
      await this.humanScroll(page, 'down');
      await this.randomDelay(1000, 2000);
      await this.humanScroll(page, 'up');
    }
  }

  async randomDelay(min: number, max: number): Promise<void> {
    const delay = Math.floor(Math.random() * (max - min + 1)) + min;
    
    // Add randomization if enabled
    if (this.config.stealth.randomizeTimings) {
      const variance = delay * 0.2; // ±20%
      const finalDelay = delay + (Math.random() * variance * 2 - variance);
      await new Promise(resolve => setTimeout(resolve, Math.max(0, finalDelay)));
    } else {
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  getRandomUserAgent(): string {
    const userAgents = [
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    ];

    return userAgents[Math.floor(Math.random() * userAgents.length)];
  }

  async waitForNetworkIdle(page: Page, timeout: number = 5000): Promise<void> {
    try {
      await page.waitForLoadState('networkidle', { timeout });
    } catch (error) {
      // Continue if timeout
    }
  }

  async detectCaptcha(page: Page): Promise<boolean> {
    try {
      const captchaSelectors = [
        '#px-captcha',
        '.g-recaptcha',
        '[data-test="captcha"]',
        'iframe[src*="recaptcha"]',
        'iframe[src*="captcha"]',
        '[class*="captcha"]',
        '[id*="captcha"]',
      ];

      for (const selector of captchaSelectors) {
        const element = await page.$(selector);
        if (element) {
          return true;
        }
      }

      // Check for common CAPTCHA text
      const bodyText = await page.textContent('body').catch(() => '');
      const captchaKeywords = ['captcha', 'verify you are human', 'unusual activity', 'security check'];
      
      if (bodyText) {
        for (const keyword of captchaKeywords) {
          if (bodyText.toLowerCase().includes(keyword)) {
            return true;
          }
        }
      }

      return false;
    } catch (error) {
      return false;
    }
  }

  async detectWarning(page: Page): Promise<boolean> {
    try {
      const bodyText = await page.textContent('body').catch(() => '');
      const warningKeywords = [
        'unusual activity',
        'temporarily restricted',
        'verify your identity',
        'security verification',
        'suspicious activity',
      ];

      if (bodyText) {
        for (const keyword of warningKeywords) {
          if (bodyText.toLowerCase().includes(keyword)) {
            return true;
          }
        }
      }

      return false;
    } catch (error) {
      return false;
    }
  }
}

export default StealthUtilities;
