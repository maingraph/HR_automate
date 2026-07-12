/**
 * Text manipulation utilities for data extraction
 */

/**
 * Sanitizes text by removing extra whitespace, newlines, and tabs
 * @param text - The text to sanitize
 * @returns Cleaned text with normalized whitespace
 */
export function sanitizeText(text: string): string {
  return text
    .trim()
    .replace(/\s+/g, ' ')
    .replace(/\n/g, ' ')
    .replace(/\t/g, ' ')
    .trim();
}

/**
 * Performs fuzzy matching between two strings
 * Handles variations like middle initials, extra spaces, etc.
 * @param str1 - First string to compare
 * @param str2 - Second string to compare
 * @returns True if strings match closely enough
 */
export function fuzzyMatch(str1: string, str2: string): boolean {
  if (!str1 || !str2) return false;
  
  const normalize = (s: string) => s.toLowerCase().trim().replace(/\s+/g, ' ');
  const s1 = normalize(str1);
  const s2 = normalize(str2);
  
  // Exact match
  if (s1 === s2) return true;
  
  // One contains the other
  if (s1.includes(s2) || s2.includes(s1)) return true;
  
  // Check if major words match (for names like "John Smith" vs "John A. Smith")
  const words1 = s1.split(' ').filter(w => w.length > 2);
  const words2 = s2.split(' ').filter(w => w.length > 2);
  
  if (words1.length === 0 || words2.length === 0) return false;
  
  const matchingWords = words1.filter(w => words2.includes(w));
  
  // At least 70% of words should match
  return matchingWords.length >= Math.min(words1.length, words2.length) * 0.7;
}

/**
 * Normalizes a URL by removing trailing slashes and query parameters
 * @param url - The URL to normalize
 * @returns Normalized URL
 */
export function normalizeUrl(url: string): string {
  if (!url) return '';
  
  try {
    const urlObj = new URL(url);
    // Remove trailing slash and query parameters
    return urlObj.origin + urlObj.pathname.replace(/\/$/, '');
  } catch {
    // If URL parsing fails, just clean up basic formatting
    return url.trim().replace(/\/$/, '').split('?')[0];
  }
}
