import { Page, ElementHandle } from 'playwright';

export interface ExperienceEntry {
  title: string;
  company: string;
  duration: string;
  location?: string;
  description?: string;
}

export interface EducationEntry {
  school: string;
  degree?: string;
  field?: string;
  duration?: string;
}

export interface SkillEntry {
  name: string;
  endorsements?: number;
}

export interface LanguageEntry {
  name: string;
  proficiency?: string;
}

export interface ProfileData {
  fullName: string;
  headline: string;
  currentCompany: string;
  location: string;
  profileUrl: string;
  profileImageUrl: string;
  connectionDegree: string;
  isPremium: boolean;
  sharedConnections: number;
  yearsAtCompany?: string;
  industry?: string;
  about?: string;
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  skills?: SkillEntry[];
  languages?: LanguageEntry[];
  possibleDuplicate?: boolean;
  scrapedAt: string;
}

export interface ScraperConfig {
  delays: {
    betweenProfiles: { min: number; max: number };
    scrolling: { min: number; max: number };
    pageLoad: { min: number; max: number };
    mouseMovement: { min: number; max: number };
  };
  breaks: {
    afterProfiles: number;
    duration: { min: number; max: number };
  };
  limits: {
    maxProfilesPerSession: number;
    maxPagesPerSession: number;
    maxProfilesPerPage: number;
  };
  browser: {
    headless: boolean;
    executablePath: string;
    userDataDir: string;
  };
  stealth: {
    enableMouseMovements: boolean;
    enableRandomScrolling: boolean;
    enablePageInteractions: boolean;
    randomizeTimings: boolean;
  };
  notifications: {
    playSound: boolean;
    showSystemNotification: boolean;
  };
  logging: {
    level: string;
    detailedOutput: boolean;
    saveToFile: boolean;
  };
}

export interface ScraperOptions {
  url?: string;
  maxProfiles?: number;
  maxPages?: number;
  test?: boolean;
  resume?: boolean;
  clearHistory?: boolean;
  listProfiles?: boolean;
  noSound?: boolean;
  configPath?: string;
  fresh?: boolean;
  noDedup?: boolean;
}

export interface Checkpoint {
  sessionId: string;
  searchUrl: string;
  currentPage: number;
  profilesScraped: number;
  lastProfileUrl: string;
  timestamp: string;
  csvFilename: string;
}

export interface ScrapedUrlsData {
  searchUrlHash: string;
  scrapedUrls: string[];
  lastUpdated: string;
}

export type DelayType = 'betweenProfiles' | 'scrolling' | 'pageLoad' | 'mouseMovement';

export interface SessionStats {
  totalProfiles: number;
  profilesSkipped: number;
  pagesScraped: number;
  sessionDuration: number;
  startTime: string;
  endTime: string;
  errors: number;
  warnings: number;
}
