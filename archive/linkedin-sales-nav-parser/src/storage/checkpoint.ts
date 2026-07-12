import * as fs from 'fs';
import * as path from 'path';
import { Checkpoint } from '../core/types';
import Logger from '../utils/logger';

class CheckpointManager {
  private checkpointPath: string;
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
    this.checkpointPath = path.join(process.cwd(), 'data', 'checkpoint.json');
    
    // Ensure data directory exists
    const dataDir = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
  }

  async saveCheckpoint(checkpoint: Checkpoint): Promise<void> {
    try {
      fs.writeFileSync(this.checkpointPath, JSON.stringify(checkpoint, null, 2));
    } catch (error) {
      this.logger.error('Failed to save checkpoint', error as Error);
    }
  }

  async loadCheckpoint(): Promise<Checkpoint | null> {
    try {
      if (!fs.existsSync(this.checkpointPath)) {
        return null;
      }

      const data = fs.readFileSync(this.checkpointPath, 'utf-8');
      return JSON.parse(data) as Checkpoint;
    } catch (error) {
      this.logger.error('Failed to load checkpoint', error as Error);
      return null;
    }
  }

  async clearCheckpoint(): Promise<void> {
    try {
      if (fs.existsSync(this.checkpointPath)) {
        fs.unlinkSync(this.checkpointPath);
        this.logger.info('Checkpoint cleared');
      }
    } catch (error) {
      this.logger.error('Failed to clear checkpoint', error as Error);
    }
  }

  hasCheckpoint(): boolean {
    return fs.existsSync(this.checkpointPath);
  }

  async getCheckpointInfo(): Promise<string | null> {
    const checkpoint = await this.loadCheckpoint();
    if (!checkpoint) return null;

    const date = new Date(checkpoint.timestamp);
    return `Found incomplete session from ${date.toLocaleString()}\nResume from page ${checkpoint.currentPage} (${checkpoint.profilesScraped} profiles scraped)?`;
  }
}

export default CheckpointManager;
