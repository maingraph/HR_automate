import chalk from 'chalk';
import * as fs from 'fs';
import * as path from 'path';
import { ProfileData } from '../core/types';

class Logger {
  private logFilePath: string;
  private startTime: Date;

  constructor() {
    this.startTime = new Date();
    const timestamp = this.formatTimestamp(this.startTime);
    this.logFilePath = path.join(
      process.cwd(),
      'logs',
      `session_${timestamp.replace(/:/g, '-')}.log`
    );
    
    // Ensure logs directory exists
    const logsDir = path.join(process.cwd(), 'logs');
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
  }

  private formatTimestamp(date: Date): string {
    return date.toISOString().replace('T', '_').split('.')[0];
  }

  private getTimeString(): string {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }

  private writeToFile(message: string): void {
    try {
      const timestamp = new Date().toISOString();
      fs.appendFileSync(this.logFilePath, `[${timestamp}] ${message}\n`);
    } catch (error) {
      // Silently fail if file writing fails
    }
  }

  private log(level: string, message: string, color: any): void {
    const timeStr = this.getTimeString();
    const formattedMessage = `[${timeStr}] ${level}: ${message}`;
    console.log(color(formattedMessage));
    this.writeToFile(formattedMessage);
  }

  info(message: string): void {
    this.log('INFO', message, chalk.cyan);
  }

  success(message: string): void {
    this.log('SUCCESS', message, chalk.green);
  }

  warn(message: string): void {
    this.log('WARN', message, chalk.yellow);
  }

  error(message: string, error?: Error): void {
    this.log('ERROR', message, chalk.red);
    if (error) {
      console.error(chalk.red(error.stack));
      this.writeToFile(`ERROR STACK: ${error.stack}`);
    }
  }

  debug(message: string): void {
    this.log('DEBUG', message, chalk.gray);
  }

  profile(profile: ProfileData, index: number, total: number): void {
    const timeStr = this.getTimeString();
    console.log(chalk.cyan(`\n[${timeStr}] PROFILE: [${index}/${total}]`));
    console.log(chalk.white(`           Name: ${profile.fullName}`));
    console.log(chalk.white(`           Title: ${profile.headline}`));
    console.log(chalk.white(`           Company: ${profile.currentCompany}`));
    console.log(chalk.white(`           Location: ${profile.location}`));
    console.log(chalk.white(`           Connection: ${profile.connectionDegree}`));
    
    if (profile.sharedConnections > 0) {
      console.log(chalk.white(`           Shared Connections: ${profile.sharedConnections}`));
    }
    
    console.log(chalk.white(`           Premium: ${profile.isPremium ? 'Yes' : 'No'}`));
    
    if (profile.yearsAtCompany) {
      console.log(chalk.white(`           Years at Company: ${profile.yearsAtCompany}`));
    }
    
    if (profile.industry) {
      console.log(chalk.white(`           Industry: ${profile.industry}`));
    }
    
    console.log(chalk.white(`           Profile URL: ${profile.profileUrl}`));
    console.log(chalk.green(`           ✓ Extracted successfully`));

    // Write to log file
    this.writeToFile(`PROFILE [${index}/${total}]: ${profile.fullName} - ${profile.headline} at ${profile.currentCompany}`);
  }

  separator(): void {
    console.log(chalk.gray('━'.repeat(60)));
  }

  header(title: string): void {
    const border = '═'.repeat(62);
    console.log(chalk.cyan(`\n╔${border}╗`));
    console.log(chalk.cyan(`║${title.padStart(31 + title.length / 2).padEnd(62)}║`));
    console.log(chalk.cyan(`╚${border}╝\n`));
    this.writeToFile(`HEADER: ${title}`);
  }

  progress(current: number, total: number, message?: string): void {
    const percentage = Math.round((current / total) * 100);
    const barLength = 40;
    const filledLength = Math.round((barLength * current) / total);
    const bar = '█'.repeat(filledLength) + '░'.repeat(barLength - filledLength);
    
    const progressMsg = message 
      ? `[${bar}] ${percentage}% - ${message}`
      : `[${bar}] ${percentage}% (${current}/${total})`;
    
    process.stdout.write('\r' + chalk.cyan(progressMsg));
    
    if (current === total) {
      console.log(); // New line when complete
    }
  }

  summary(stats: {
    totalProfiles: number;
    profilesSkipped: number;
    pagesScraped: number;
    sessionDuration: string;
    csvFile: string;
    logFile: string;
    errors: number;
    warnings: number;
  }): void {
    const border = '═'.repeat(62);
    console.log(chalk.green(`\n╔${border}╗`));
    console.log(chalk.green(`║${'SCRAPING COMPLETE! 🎉'.padStart(41).padEnd(62)}║`));
    console.log(chalk.green(`╚${border}╝\n`));

    console.log(chalk.cyan('📊 Session Summary:'));
    console.log(chalk.white(`   • Total profiles extracted: ${stats.totalProfiles}`));
    console.log(chalk.white(`   • Profiles skipped (duplicates): ${stats.profilesSkipped}`));
    console.log(chalk.white(`   • Pages scraped: ${stats.pagesScraped}`));
    console.log(chalk.white(`   • Session duration: ${stats.sessionDuration}`));
    
    if (stats.totalProfiles > 0) {
      const avgTime = this.calculateAverageTime(stats.sessionDuration, stats.totalProfiles);
      console.log(chalk.white(`   • Average time per profile: ${avgTime}`));
    }

    console.log(chalk.cyan('\n📁 Output:'));
    console.log(chalk.white(`   • CSV file: ${stats.csvFile}`));
    console.log(chalk.white(`   • Log file: ${stats.logFile}`));

    if (stats.errors === 0 && stats.warnings === 0) {
      console.log(chalk.green('\n✅ No errors or warnings\n'));
    } else {
      if (stats.errors > 0) {
        console.log(chalk.red(`\n⚠️  ${stats.errors} error(s) occurred`));
      }
      if (stats.warnings > 0) {
        console.log(chalk.yellow(`⚠️  ${stats.warnings} warning(s) occurred`));
      }
      console.log();
    }

    this.writeToFile(`SESSION SUMMARY: ${stats.totalProfiles} profiles, ${stats.pagesScraped} pages, ${stats.sessionDuration}`);
  }

  private calculateAverageTime(duration: string, count: number): string {
    // Parse duration string like "30 minutes 45 seconds"
    const parts = duration.split(' ');
    let totalSeconds = 0;
    
    for (let i = 0; i < parts.length; i += 2) {
      const value = parseInt(parts[i]);
      const unit = parts[i + 1];
      
      if (unit.startsWith('minute')) {
        totalSeconds += value * 60;
      } else if (unit.startsWith('second')) {
        totalSeconds += value;
      } else if (unit.startsWith('hour')) {
        totalSeconds += value * 3600;
      }
    }
    
    const avgSeconds = Math.round(totalSeconds / count);
    
    if (avgSeconds < 60) {
      return `${avgSeconds} seconds`;
    } else {
      const minutes = Math.floor(avgSeconds / 60);
      const seconds = avgSeconds % 60;
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds} second${seconds !== 1 ? 's' : ''}`;
    }
  }

  getLogFilePath(): string {
    return this.logFilePath;
  }

  getSessionDuration(): string {
    const now = new Date();
    const durationMs = now.getTime() - this.startTime.getTime();
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours} hour${hours !== 1 ? 's' : ''} ${minutes % 60} minute${minutes % 60 !== 1 ? 's' : ''} ${seconds % 60} second${seconds % 60 !== 1 ? 's' : ''}`;
    } else if (minutes > 0) {
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds % 60} second${seconds % 60 !== 1 ? 's' : ''}`;
    } else {
      return `${seconds} second${seconds !== 1 ? 's' : ''}`;
    }
  }
}

export default Logger;
