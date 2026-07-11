import { exec } from 'child_process';
import { promisify } from 'util';
import Logger from './logger';

const execAsync = promisify(exec);

class Notifier {
  private logger: Logger;
  private soundEnabled: boolean;

  constructor(logger: Logger, soundEnabled: boolean = true) {
    this.logger = logger;
    this.soundEnabled = soundEnabled;
  }

  async playCompletionSound(): Promise<void> {
    if (!this.soundEnabled) return;

    try {
      // Use macOS afplay to play system sound
      await execAsync('afplay /System/Library/Sounds/Glass.aiff');
    } catch (error) {
      // Fallback to terminal bell
      process.stdout.write('\x07');
    }
  }

  async playErrorSound(): Promise<void> {
    if (!this.soundEnabled) return;

    try {
      // Use macOS afplay to play system sound
      await execAsync('afplay /System/Library/Sounds/Basso.aiff');
    } catch (error) {
      // Fallback to terminal bell
      process.stdout.write('\x07');
    }
  }

  async showNotification(title: string, message: string): Promise<void> {
    try {
      // Use macOS osascript to show notification
      const script = `display notification "${message}" with title "${title}"`;
      await execAsync(`osascript -e '${script}'`);
    } catch (error) {
      // Silently fail if notification fails
    }
  }

  async notifyCompletion(profileCount: number): Promise<void> {
    await this.playCompletionSound();
    await this.showNotification(
      'LinkedIn Scraper Complete',
      `Successfully scraped ${profileCount} profiles`
    );
    this.logger.info('🔔 Completion notification sent');
  }

  async notifyError(errorMessage: string): Promise<void> {
    await this.playErrorSound();
    await this.showNotification(
      'LinkedIn Scraper Error',
      errorMessage
    );
  }
}

export default Notifier;
