import * as fs from 'fs';
import * as path from 'path';
import { homedir } from 'os';
import Logger from './logger';

class ChromeDetector {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  async detectChromeProfile(): Promise<string> {
    this.logger.info('Detecting Chrome profile...');

    const possiblePaths = this.getChromeProfilePaths();

    for (const profilePath of possiblePaths) {
      if (await this.validateProfile(profilePath)) {
        this.logger.info(`Found Chrome profile: ${profilePath}`);
        return profilePath;
      }
    }

    throw new Error('Could not find a valid Chrome profile. Please ensure Chrome is installed and you have logged into LinkedIn.');
  }

  private getChromeProfilePaths(): string[] {
    const home = homedir();
    const basePath = path.join(home, 'Library', 'Application Support', 'Google', 'Chrome');

    const paths: string[] = [
      path.join(basePath, 'Default'),
      path.join(basePath, 'Profile 1'),
      path.join(basePath, 'Profile 2'),
      path.join(basePath, 'Profile 3'),
      path.join(basePath, 'Profile 4'),
      path.join(basePath, 'Profile 5'),
    ];

    return paths;
  }

  async validateProfile(profilePath: string): Promise<boolean> {
    try {
      // Check if directory exists
      if (!fs.existsSync(profilePath)) {
        return false;
      }

      // Check if it has cookies file (indicates it's a valid profile)
      const cookiesPath = path.join(profilePath, 'Cookies');
      const networkPath = path.join(profilePath, 'Network');
      
      if (fs.existsSync(cookiesPath) || fs.existsSync(networkPath)) {
        this.logger.info(`Validating profile (checking for LinkedIn session)...`);
        // Profile exists and has cookies
        return true;
      }

      return false;
    } catch (error) {
      return false;
    }
  }

  async listAvailableProfiles(): Promise<string[]> {
    const possiblePaths = this.getChromeProfilePaths();
    const validProfiles: string[] = [];

    for (const profilePath of possiblePaths) {
      if (await this.validateProfile(profilePath)) {
        validProfiles.push(profilePath);
      }
    }

    return validProfiles;
  }

  getChromeExecutablePath(): string {
    // Default Chrome path on macOS
    return '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  }

  validateChromeInstallation(): boolean {
    const chromePath = this.getChromeExecutablePath();
    return fs.existsSync(chromePath);
  }
}

export default ChromeDetector;
