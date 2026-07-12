import * as fs from 'fs';
import * as path from 'path';
import { createObjectCsvWriter } from 'csv-writer';
import { ProfileData } from '../core/types';
import Logger from '../utils/logger';

class CSVExporter {
  private logger: Logger;
  private outputDir: string;

  constructor(logger: Logger) {
    this.logger = logger;
    this.outputDir = path.join(process.cwd(), 'output');
    
    // Ensure output directory exists
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  async exportToCSV(profiles: ProfileData[], filename?: string): Promise<string> {
    try {
      const csvFilename = filename || this.generateFilename();
      const csvPath = path.join(this.outputDir, csvFilename);

      const csvWriter = createObjectCsvWriter({
        path: csvPath,
        header: [
          { id: 'fullName', title: 'Full Name' },
          { id: 'headline', title: 'Headline' },
          { id: 'currentCompany', title: 'Current Company' },
          { id: 'location', title: 'Location' },
          { id: 'profileUrl', title: 'LinkedIn Profile URL' },
          { id: 'profileImageUrl', title: 'Profile Image URL' },
          { id: 'connectionDegree', title: 'Connection Degree' },
          { id: 'isPremium', title: 'Premium Badge' },
          { id: 'sharedConnections', title: 'Shared Connections' },
          { id: 'yearsAtCompany', title: 'Years at Company' },
          { id: 'industry', title: 'Industry' },
          { id: 'about', title: 'About' },
          { id: 'experience', title: 'Experience' },
          { id: 'education', title: 'Education' },
          { id: 'skills', title: 'Skills' },
          { id: 'languages', title: 'Languages' },
          { id: 'possibleDuplicate', title: 'Possible Duplicate' },
          { id: 'scrapedAt', title: 'Scraped At' },
        ],
      });

      // Format profiles for CSV
      const formattedProfiles = profiles.map(profile => this.formatProfileForCSV(profile));

      await csvWriter.writeRecords(formattedProfiles);

      this.logger.info(`CSV exported successfully: ${csvPath}`);
      return csvPath;
    } catch (error) {
      this.logger.error('Failed to export CSV', error as Error);
      throw error;
    }
  }

  async appendToCSV(profiles: ProfileData[], filename: string): Promise<void> {
    try {
      const csvPath = path.join(this.outputDir, filename);

      const csvWriter = createObjectCsvWriter({
        path: csvPath,
        header: [
          { id: 'fullName', title: 'Full Name' },
          { id: 'headline', title: 'Headline' },
          { id: 'currentCompany', title: 'Current Company' },
          { id: 'location', title: 'Location' },
          { id: 'profileUrl', title: 'LinkedIn Profile URL' },
          { id: 'profileImageUrl', title: 'Profile Image URL' },
          { id: 'connectionDegree', title: 'Connection Degree' },
          { id: 'isPremium', title: 'Premium Badge' },
          { id: 'sharedConnections', title: 'Shared Connections' },
          { id: 'yearsAtCompany', title: 'Years at Company' },
          { id: 'industry', title: 'Industry' },
          { id: 'about', title: 'About' },
          { id: 'experience', title: 'Experience' },
          { id: 'education', title: 'Education' },
          { id: 'skills', title: 'Skills' },
          { id: 'languages', title: 'Languages' },
          { id: 'possibleDuplicate', title: 'Possible Duplicate' },
          { id: 'scrapedAt', title: 'Scraped At' },
        ],
        append: true,
      });

      const formattedProfiles = profiles.map(profile => this.formatProfileForCSV(profile));
      await csvWriter.writeRecords(formattedProfiles);

      this.logger.info(`Appended ${profiles.length} profiles to CSV`);
    } catch (error) {
      this.logger.error('Failed to append to CSV', error as Error);
      throw error;
    }
  }

  generateFilename(): string {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    return `linkedin_export_${year}-${month}-${day}_${hours}-${minutes}-${seconds}.csv`;
  }

  private formatProfileForCSV(profile: ProfileData): Record<string, string> {
    return {
      fullName: profile.fullName,
      headline: profile.headline,
      currentCompany: profile.currentCompany,
      location: profile.location,
      profileUrl: profile.profileUrl,
      profileImageUrl: profile.profileImageUrl,
      connectionDegree: profile.connectionDegree,
      isPremium: profile.isPremium ? 'Yes' : 'No',
      sharedConnections: profile.sharedConnections.toString(),
      yearsAtCompany: profile.yearsAtCompany || '',
      industry: profile.industry || '',
      about: profile.about || '',
      experience: profile.experience ? JSON.stringify(profile.experience) : '',
      education: profile.education ? JSON.stringify(profile.education) : '',
      skills: profile.skills ? JSON.stringify(profile.skills) : '',
      languages: profile.languages ? JSON.stringify(profile.languages) : '',
      possibleDuplicate: profile.possibleDuplicate ? 'Yes' : 'No',
      scrapedAt: profile.scrapedAt,
    };
  }

  getOutputPath(filename: string): string {
    return path.join(this.outputDir, filename);
  }
}

export default CSVExporter;
