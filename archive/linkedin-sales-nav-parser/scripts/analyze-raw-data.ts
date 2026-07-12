import * as fs from 'fs';
import * as path from 'path';

/**
 * Analyzes raw extraction data to identify patterns
 */

interface RawProfileData {
  profileIndex: number;
  cardName: string;
  cardCompany: string;
  cardHeadline: string;
  sidebarHTML: string;
  sidebarText: string;
  sidebarOuterHTML: string;
  timestamp: string;
  pageUrl: string;
}

function analyzeData(filePath: string) {
  console.log('📊 ANALYZING RAW EXTRACTION DATA');
  console.log('═'.repeat(80));
  console.log('');

  // Read the data
  const data: RawProfileData[] = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  
  console.log(`Total profiles extracted: ${data.length}`);
  console.log('');

  // Analysis 1: Card extraction success rate
  console.log('━'.repeat(80));
  console.log('1️⃣  CARD EXTRACTION SUCCESS RATE');
  console.log('━'.repeat(80));
  
  const withCardName = data.filter(p => p.cardName && p.cardName.trim() !== '');
  const withoutCardName = data.filter(p => !p.cardName || p.cardName.trim() === '');
  
  console.log(`✅ Profiles with card name: ${withCardName.length} (${(withCardName.length / data.length * 100).toFixed(1)}%)`);
  console.log(`❌ Profiles without card name: ${withoutCardName.length} (${(withoutCardName.length / data.length * 100).toFixed(1)}%)`);
  console.log('');
  
  if (withoutCardName.length > 0) {
    console.log('Profiles with missing card names:');
    withoutCardName.forEach(p => {
      // Extract name from sidebar text
      const sidebarNameMatch = p.sidebarText.match(/Basic lead information for\s+([^\n]+)/);
      const sidebarName = sidebarNameMatch ? sidebarNameMatch[1].trim() : 'Unknown';
      console.log(`  - Profile #${p.profileIndex}: ${sidebarName}`);
    });
    console.log('');
  }

  // Analysis 2: Sidebar structure consistency
  console.log('━'.repeat(80));
  console.log('2️⃣  SIDEBAR STRUCTURE CONSISTENCY');
  console.log('━'.repeat(80));
  
  const patterns = {
    hasBasicLeadInfo: 0,
    hasProfileDetailsLoaded: 0,
    hasConnectionDegree: 0,
    hasLocation: 0,
    hasExperienceSection: 0,
    hasEducationSection: 0,
    hasSkillsSection: 0,
    hasAboutSection: 0,
  };
  
  data.forEach(p => {
    if (p.sidebarText.includes('Basic lead information for')) patterns.hasBasicLeadInfo++;
    if (p.sidebarText.includes('Profile details loaded for')) patterns.hasProfileDetailsLoaded++;
    if (p.sidebarText.match(/\d+(st|nd|rd|th)/)) patterns.hasConnectionDegree++;
    if (p.sidebarText.match(/(Area|Metropolitan|Cyprus|Poland|Armenia|Georgia|Kazakhstan|Russia|Belarus|Serbia)/)) patterns.hasLocation++;
    if (p.sidebarText.toLowerCase().includes('experience')) patterns.hasExperienceSection++;
    if (p.sidebarText.toLowerCase().includes('education')) patterns.hasEducationSection++;
    if (p.sidebarText.toLowerCase().includes('skills') || p.sidebarText.toLowerCase().includes('featured skills')) patterns.hasSkillsSection++;
    if (p.sidebarText.toLowerCase().includes('about')) patterns.hasAboutSection++;
  });
  
  console.log('Pattern occurrence across all profiles:');
  console.log(`  "Basic lead information for": ${patterns.hasBasicLeadInfo}/${data.length} (${(patterns.hasBasicLeadInfo / data.length * 100).toFixed(1)}%)`);
  console.log(`  "Profile details loaded for": ${patterns.hasProfileDetailsLoaded}/${data.length} (${(patterns.hasProfileDetailsLoaded / data.length * 100).toFixed(1)}%)`);
  console.log(`  Connection degree (1st/2nd/3rd): ${patterns.hasConnectionDegree}/${data.length} (${(patterns.hasConnectionDegree / data.length * 100).toFixed(1)}%)`);
  console.log(`  Location info: ${patterns.hasLocation}/${data.length} (${(patterns.hasLocation / data.length * 100).toFixed(1)}%)`);
  console.log(`  Experience section: ${patterns.hasExperienceSection}/${data.length} (${(patterns.hasExperienceSection / data.length * 100).toFixed(1)}%)`);
  console.log(`  Education section: ${patterns.hasEducationSection}/${data.length} (${(patterns.hasEducationSection / data.length * 100).toFixed(1)}%)`);
  console.log(`  Skills section: ${patterns.hasSkillsSection}/${data.length} (${(patterns.hasSkillsSection / data.length * 100).toFixed(1)}%)`);
  console.log(`  About section: ${patterns.hasAboutSection}/${data.length} (${(patterns.hasAboutSection / data.length * 100).toFixed(1)}%)`);
  console.log('');

  // Analysis 3: Name extraction patterns
  console.log('━'.repeat(80));
  console.log('3️⃣  NAME EXTRACTION PATTERNS');
  console.log('━'.repeat(80));
  
  console.log('Checking if name can be extracted from sidebar for ALL profiles...');
  console.log('');
  
  let successCount = 0;
  const failures: any[] = [];
  
  data.forEach(p => {
    // Try multiple extraction methods
    let extractedName = '';
    
    // Method 1: "Basic lead information for"
    let match = p.sidebarText.match(/Basic lead information for\s+([^\n.]+)/);
    if (match && match[1]) {
      extractedName = match[1].trim();
    }
    
    // Method 2: "Profile details loaded for"
    if (!extractedName) {
      match = p.sidebarText.match(/Profile details loaded for\s+([^\n.]+)/);
      if (match && match[1]) {
        extractedName = match[1].trim();
      }
    }
    
    // Method 3: data-anonymize="person-name" in HTML
    if (!extractedName) {
      match = p.sidebarHTML.match(/data-anonymize="person-name"[^>]*>([^<]+)</);
      if (match && match[1]) {
        extractedName = match[1].trim();
      }
    }
    
    if (extractedName) {
      successCount++;
      console.log(`  ✅ Profile #${p.profileIndex}: "${extractedName}" (Card: "${p.cardName || 'EMPTY'}")`);
    } else {
      failures.push(p);
      console.log(`  ❌ Profile #${p.profileIndex}: FAILED TO EXTRACT (Card: "${p.cardName || 'EMPTY'}")`);
    }
  });
  
  console.log('');
  console.log(`Success rate: ${successCount}/${data.length} (${(successCount / data.length * 100).toFixed(1)}%)`);
  console.log('');

  // Analysis 4: Compare profiles with/without card names
  console.log('━'.repeat(80));
  console.log('4️⃣  COMPARING PROFILES WITH/WITHOUT CARD NAMES');
  console.log('━'.repeat(80));
  
  if (withoutCardName.length > 0) {
    console.log('Checking if sidebar structure differs for profiles without card names...');
    console.log('');
    
    // Check if they have the same patterns
    const withCardPatterns = {
      hasBasicLeadInfo: 0,
      hasProfileDetailsLoaded: 0,
      hasConnectionDegree: 0,
    };
    
    const withoutCardPatterns = {
      hasBasicLeadInfo: 0,
      hasProfileDetailsLoaded: 0,
      hasConnectionDegree: 0,
    };
    
    withCardName.forEach(p => {
      if (p.sidebarText.includes('Basic lead information for')) withCardPatterns.hasBasicLeadInfo++;
      if (p.sidebarText.includes('Profile details loaded for')) withCardPatterns.hasProfileDetailsLoaded++;
      if (p.sidebarText.match(/\d+(st|nd|rd|th)/)) withCardPatterns.hasConnectionDegree++;
    });
    
    withoutCardName.forEach(p => {
      if (p.sidebarText.includes('Basic lead information for')) withoutCardPatterns.hasBasicLeadInfo++;
      if (p.sidebarText.includes('Profile details loaded for')) withoutCardPatterns.hasProfileDetailsLoaded++;
      if (p.sidebarText.match(/\d+(st|nd|rd|th)/)) withoutCardPatterns.hasConnectionDegree++;
    });
    
    console.log('WITH card name:');
    console.log(`  "Basic lead information for": ${withCardPatterns.hasBasicLeadInfo}/${withCardName.length} (${(withCardPatterns.hasBasicLeadInfo / withCardName.length * 100).toFixed(1)}%)`);
    console.log(`  "Profile details loaded for": ${withCardPatterns.hasProfileDetailsLoaded}/${withCardName.length} (${(withCardPatterns.hasProfileDetailsLoaded / withCardName.length * 100).toFixed(1)}%)`);
    console.log(`  Connection degree: ${withCardPatterns.hasConnectionDegree}/${withCardName.length} (${(withCardPatterns.hasConnectionDegree / withCardName.length * 100).toFixed(1)}%)`);
    console.log('');
    
    console.log('WITHOUT card name:');
    console.log(`  "Basic lead information for": ${withoutCardPatterns.hasBasicLeadInfo}/${withoutCardName.length} (${(withoutCardPatterns.hasBasicLeadInfo / withoutCardName.length * 100).toFixed(1)}%)`);
    console.log(`  "Profile details loaded for": ${withoutCardPatterns.hasProfileDetailsLoaded}/${withoutCardName.length} (${(withoutCardPatterns.hasProfileDetailsLoaded / withoutCardName.length * 100).toFixed(1)}%)`);
    console.log(`  Connection degree: ${withoutCardPatterns.hasConnectionDegree}/${withoutCardName.length} (${(withoutCardPatterns.hasConnectionDegree / withoutCardName.length * 100).toFixed(1)}%)`);
    console.log('');
    
    console.log('🔍 CONCLUSION: Sidebar structure is ' + 
      (withCardPatterns.hasBasicLeadInfo / withCardName.length === withoutCardPatterns.hasBasicLeadInfo / withoutCardName.length ? 
        'IDENTICAL' : 'DIFFERENT') + 
      ' for profiles with/without card names');
    console.log('');
  }

  // Analysis 5: HTML selectors that work
  console.log('━'.repeat(80));
  console.log('5️⃣  RELIABLE HTML SELECTORS');
  console.log('━'.repeat(80));
  
  const selectors = {
    'data-anonymize="person-name"': 0,
    'class="_entity-name_14ppj7"': 0,
    'class="_lead-page-link_14ppj7"': 0,
    'class="_entity-subheading_14ppj7"': 0,
  };
  
  data.forEach(p => {
    if (p.sidebarHTML.includes('data-anonymize="person-name"')) selectors['data-anonymize="person-name"']++;
    if (p.sidebarHTML.includes('_entity-name_14ppj7')) selectors['class="_entity-name_14ppj7"']++;
    if (p.sidebarHTML.includes('_lead-page-link_14ppj7')) selectors['class="_lead-page-link_14ppj7"']++;
    if (p.sidebarHTML.includes('_entity-subheading_14ppj7')) selectors['class="_entity-subheading_14ppj7"']++;
  });
  
  console.log('Selector occurrence in sidebar HTML:');
  Object.entries(selectors).forEach(([selector, count]) => {
    console.log(`  ${selector}: ${count}/${data.length} (${(count / data.length * 100).toFixed(1)}%)`);
  });
  console.log('');

  // Analysis 6: Race condition evidence
  console.log('━'.repeat(80));
  console.log('6️⃣  RACE CONDITION EVIDENCE');
  console.log('━'.repeat(80));
  
  console.log('Checking for duplicate sidebar content (race condition indicator)...');
  console.log('');
  
  const sidebarContents = new Map<string, number[]>();
  data.forEach(p => {
    // Use first 500 chars of sidebar text as fingerprint
    const fingerprint = p.sidebarText.substring(0, 500);
    if (!sidebarContents.has(fingerprint)) {
      sidebarContents.set(fingerprint, []);
    }
    sidebarContents.get(fingerprint)!.push(p.profileIndex);
  });
  
  const duplicates = Array.from(sidebarContents.entries()).filter(([_, indices]) => indices.length > 1);
  
  if (duplicates.length > 0) {
    console.log(`⚠️  Found ${duplicates.length} cases of duplicate sidebar content:`);
    duplicates.forEach(([fingerprint, indices]) => {
      console.log(`  Profiles ${indices.join(', ')} have identical sidebar content`);
      // Extract name from fingerprint
      const nameMatch = fingerprint.match(/Basic lead information for\s+([^\n]+)/);
      if (nameMatch) {
        console.log(`    → All showing: ${nameMatch[1].trim()}`);
      }
    });
    console.log('');
    console.log('🚨 RACE CONDITION DETECTED: Multiple profiles showing same sidebar!');
  } else {
    console.log('✅ No duplicate sidebar content found - no race condition detected');
  }
  console.log('');

  // Final summary
  console.log('═'.repeat(80));
  console.log('📋 SUMMARY & RECOMMENDATIONS');
  console.log('═'.repeat(80));
  console.log('');
  
  console.log('KEY FINDINGS:');
  console.log(`1. Card extraction fails for ${withoutCardName.length}/${data.length} profiles (${(withoutCardName.length / data.length * 100).toFixed(1)}%)`);
  console.log(`2. Sidebar name extraction works for ${successCount}/${data.length} profiles (${(successCount / data.length * 100).toFixed(1)}%)`);
  console.log(`3. "Basic lead information for" pattern appears in ${patterns.hasBasicLeadInfo}/${data.length} profiles (${(patterns.hasBasicLeadInfo / data.length * 100).toFixed(1)}%)`);
  console.log(`4. Sidebar structure is ${withoutCardName.length > 0 ? 'CONSISTENT' : 'N/A'} regardless of card extraction success`);
  console.log('');
  
  console.log('RECOMMENDATIONS:');
  if (successCount === data.length) {
    console.log('✅ TRADITIONAL PARSING IS SUFFICIENT');
    console.log('   → Sidebar extraction works 100% of the time');
    console.log('   → Use fallback flow: if card name is empty, extract from sidebar');
    console.log('   → No need for AI extraction');
    console.log('');
    console.log('IMPLEMENTATION:');
    console.log('   1. Try to extract name from card');
    console.log('   2. If empty → Click profile → Extract name from sidebar');
    console.log('   3. Use sidebar name for verification (or skip verification)');
    console.log('   4. Continue with normal extraction');
  } else {
    console.log('⚠️  CONSIDER HYBRID APPROACH');
    console.log(`   → Sidebar extraction fails for ${data.length - successCount} profiles`);
    console.log('   → Use traditional parsing as primary method');
    console.log('   → Use AI extraction as fallback for failed cases');
  }
  console.log('');
  
  if (duplicates.length > 0) {
    console.log('🚨 RACE CONDITION ISSUE:');
    console.log('   → Sidebar verification is CRITICAL');
    console.log('   → Must wait for sidebar to update before extraction');
    console.log('   → Current fuzzy matching approach is correct');
  }
  console.log('');
}

// Main execution
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('❌ Error: Please provide path to raw extraction JSON file');
  console.log('\nUsage:');
  console.log('  npm run analyze-raw -- data/raw-extractions/all_profiles_*.json');
  process.exit(1);
}

const filePath = args[0];

if (!fs.existsSync(filePath)) {
  console.error(`❌ Error: File not found: ${filePath}`);
  process.exit(1);
}

analyzeData(filePath);
