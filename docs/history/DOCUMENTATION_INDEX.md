# Sourcer Documentation Index

> **Central index for all project documentation**  
> **Last Updated:** 2026-04-27T09:12:00Z

---

## 📚 Documentation Structure

```
sourcer/
├── README.md                      # Project overview & quick start
├── ARCHITECTURE.md                # Complete technical documentation
├── REFACTORING_CHANGELOG.md      # Detailed refactoring history
├── CLAUDE_ARCH_CONTEXT.md        # Claude Opus original notes (historical)
├── ANTIGRAVITY_FIX_LOG.md        # Gemini 3.1 fixes (historical)
└── DOCUMENTATION_INDEX.md        # This file
```

---

## 🎯 Quick Navigation

### For New Developers
1. Start with [README.md](./README.md) — Overview and quick start
2. Read [ARCHITECTURE.md § 1-3](./ARCHITECTURE.md) — Vision, tech stack, structure
3. Review [ARCHITECTURE.md § 6](./ARCHITECTURE.md) — Critical algorithms
4. Check [REFACTORING_CHANGELOG.md](./REFACTORING_CHANGELOG.md) — Recent changes

### For Debugging
1. [ARCHITECTURE.md § 17](./ARCHITECTURE.md#17-troubleshooting-guide) — Troubleshooting
2. [ARCHITECTURE.md § 9](./ARCHITECTURE.md#9-known-issues--fragile-areas) — Known issues
3. [README.md § Troubleshooting](./README.md#-troubleshooting) — Common problems

### For Refactoring
1. [ARCHITECTURE.md § 16](./ARCHITECTURE.md#16-style-guide-post-refactoring) — Style guide
2. [REFACTORING_CHANGELOG.md](./REFACTORING_CHANGELOG.md) — Past refactorings
3. [ARCHITECTURE.md § 4](./ARCHITECTURE.md#4-recent-refactoring-phase-1--april-2026) — Latest changes

### For Deployment
1. [README.md § Quick Start](./README.md#-quick-start) — Launch instructions
2. [ARCHITECTURE.md § 7](./ARCHITECTURE.md#7-environment-variables) — Environment config
3. [ARCHITECTURE.md § 18](./ARCHITECTURE.md#18-maintenance-checklist) — Maintenance

---

## 📖 Document Descriptions

### README.md (300 lines)
**Purpose:** Project overview, quick start, basic troubleshooting

**Contents:**
- Quick start guide
- Tech stack overview
- How it works (high-level)
- Environment variables
- Project structure
- Troubleshooting basics
- Roadmap

**Audience:** New developers, operators

**When to read:** First time setup, quick reference

---

### ARCHITECTURE.md (1,000+ lines)
**Purpose:** Complete technical documentation and reference

**Contents:**
- Technical vision and goals
- Complete tech stack with versions
- Detailed folder structure
- Phase 1 refactoring details (April 2026)
- Historical bug fixes
- Complex algorithms (two-stage scoring, key rotation, deduplication)
- Environment variables (complete list)
- Database schema
- Known issues and fragile areas
- Unimplemented features
- Process flow diagrams
- Development history (Claude → Gemini → OpenCode)
- Testing and validation
- Future roadmap
- Detailed refactoring log
- Style guide
- Troubleshooting guide
- Maintenance checklist

**Audience:** Developers, architects, future AI agents

**When to read:** 
- Understanding system architecture
- Debugging complex issues
- Planning refactoring
- Onboarding new team members

**Key Sections:**
- § 6: Complex Algorithms (MUST READ before modifying scoring)
- § 9: Known Issues (MUST READ before deployment)
- § 16: Style Guide (MUST READ before contributing)
- § 17: Troubleshooting (MUST READ when debugging)

---

### REFACTORING_CHANGELOG.md (300 lines)
**Purpose:** Detailed changelog of all refactoring sessions

**Contents:**
- Phase 1: Backend Clean Development (April 2026)
  - Objectives, changes, testing, metrics
- Phase 2: Gemini 3.1 / Antigravity (Dec 2025 - Mar 2026)
  - Dynamic prompts, admin dashboard, key rotation
- Phase 3: Claude Opus Foundation (Jun 2024 - Nov 2025)
  - Core architecture, scoring pipeline, frontend
- Future planned refactoring
- Refactoring principles applied
- Code quality standards

**Audience:** Developers, project managers

**When to read:**
- Before starting new refactoring
- Understanding past decisions
- Planning future work
- Code review context

---

### CLAUDE_ARCH_CONTEXT.md (441 lines) [HISTORICAL]
**Purpose:** Original architecture notes from Claude Opus

**Contents:**
- Original technical vision
- Tech stack decisions
- Folder structure rationale
- Complex algorithms (original documentation)
- Known bugs and fixes
- Environment variables
- Database schema
- Process map

**Audience:** Historical reference

**When to read:**
- Understanding original design decisions
- Comparing with current architecture
- Historical context for bugs

**Status:** Superseded by ARCHITECTURE.md but kept for historical reference

---

### ANTIGRAVITY_FIX_LOG.md (88 lines) [HISTORICAL]
**Purpose:** Bug fixes and improvements from Gemini 3.1 phase

**Contents:**
- Technical vision recap
- Folder structure
- Recent bugs fixed (Telegram SQLite, Next.js zombie, LinkedIn Apify)
- UI/UX changes (Gemini vs Sonnet)
- Fragile areas
- Complex algorithms
- Package versions
- Unimplemented features

**Audience:** Historical reference

**When to read:**
- Understanding Gemini phase changes
- Bug fix context
- Comparing approaches

**Status:** Superseded by ARCHITECTURE.md but kept for historical reference

---

## 🔍 Finding Information

### By Topic

**Architecture & Design:**
- ARCHITECTURE.md § 1-3 (Vision, Tech Stack, Structure)
- CLAUDE_ARCH_CONTEXT.md § 1-3 (Original design)

**Algorithms & Logic:**
- ARCHITECTURE.md § 6 (Complex Algorithms)
- CLAUDE_ARCH_CONTEXT.md § 4 (Original algorithms)

**Environment Setup:**
- README.md § Environment Variables
- ARCHITECTURE.md § 7 (Complete list)

**Troubleshooting:**
- README.md § Troubleshooting (Common issues)
- ARCHITECTURE.md § 17 (Detailed guide)
- ARCHITECTURE.md § 9 (Known issues)

**Refactoring:**
- REFACTORING_CHANGELOG.md (All sessions)
- ARCHITECTURE.md § 4 (Latest refactoring)
- ARCHITECTURE.md § 16 (Style guide)

**Database:**
- ARCHITECTURE.md § 8 (Schema reference)
- CLAUDE_ARCH_CONTEXT.md § 7 (Original schema)

**Deployment:**
- README.md § Quick Start
- ARCHITECTURE.md § 18 (Maintenance)

**Testing:**
- README.md § Testing
- ARCHITECTURE.md § 13 (Testing & Validation)
- REFACTORING_CHANGELOG.md (Test results)

---

## 📊 Documentation Metrics

| Document | Lines | Words | Size | Last Updated |
|----------|-------|-------|------|--------------|
| README.md | 300 | 2,500 | 9.5 KB | 2026-04-27 |
| ARCHITECTURE.md | 1,000+ | 12,000 | 30 KB | 2026-04-27 |
| REFACTORING_CHANGELOG.md | 300 | 3,000 | 8.5 KB | 2026-04-27 |
| CLAUDE_ARCH_CONTEXT.md | 441 | 5,000 | 23 KB | 2026-03-26 |
| ANTIGRAVITY_FIX_LOG.md | 88 | 1,000 | 8.1 KB | 2026-03-26 |
| **Total** | **2,129+** | **23,500+** | **79+ KB** | - |

---

## 🔄 Documentation Maintenance

### Update Frequency

**After every refactoring session:**
- [ ] Update REFACTORING_CHANGELOG.md with new entry
- [ ] Update ARCHITECTURE.md § 4 with changes
- [ ] Update README.md § Recent Changes
- [ ] Update this index if structure changes

**Monthly:**
- [ ] Review and update Known Issues
- [ ] Update metrics and statistics
- [ ] Check for outdated information
- [ ] Update roadmap progress

**Quarterly:**
- [ ] Comprehensive documentation review
- [ ] Archive old historical documents
- [ ] Reorganize if needed
- [ ] Update all "Last Updated" timestamps

### Documentation Standards

**All documents must:**
- Have clear purpose statement at top
- Include "Last Updated" timestamp
- Use consistent markdown formatting
- Include table of contents for >200 lines
- Cross-reference related documents
- Use code blocks with language tags
- Include examples where applicable

**Commit messages for docs:**
```
docs: [type] brief description

Types: add, update, fix, refactor, archive
Examples:
- docs: add troubleshooting section to README
- docs: update ARCHITECTURE with Phase 1 changes
- docs: fix broken links in index
```

---

## 🎓 Learning Path

### Week 1: Basics
1. Read README.md completely
2. Set up local environment
3. Run `bash launch.sh` and explore UI
4. Read ARCHITECTURE.md § 1-3

### Week 2: Deep Dive
1. Read ARCHITECTURE.md § 6 (Algorithms)
2. Trace code flow for one pipeline run
3. Read REFACTORING_CHANGELOG.md
4. Review database schema

### Week 3: Advanced
1. Read ARCHITECTURE.md § 9 (Known Issues)
2. Debug one issue from troubleshooting guide
3. Read style guide and refactoring principles
4. Review historical documents (Claude, Gemini)

### Week 4: Contribution Ready
1. Make small refactoring following style guide
2. Update documentation for your changes
3. Write tests for new code
4. Submit for review

---

## 📝 Contributing to Documentation

### Before Writing
1. Check if information already exists
2. Determine correct document for content
3. Review existing style and format
4. Plan structure and sections

### While Writing
1. Use clear, concise language
2. Include code examples
3. Add cross-references
4. Use consistent formatting
5. Include "Last Updated" timestamp

### After Writing
1. Proofread for clarity
2. Check all links work
3. Update this index if needed
4. Commit with descriptive message

### Documentation Review Checklist
- [ ] Purpose clearly stated
- [ ] Audience identified
- [ ] Content accurate and up-to-date
- [ ] Code examples tested
- [ ] Links verified
- [ ] Formatting consistent
- [ ] Cross-references added
- [ ] Index updated

---

## 🔗 External Resources

### Official Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Next.js Docs](https://nextjs.org/docs)
- [Celery Docs](https://docs.celeryq.dev/)
- [Supabase Docs](https://supabase.com/docs)
- [Telethon Docs](https://docs.telethon.dev/)
- [Playwright Docs](https://playwright.dev/python/)

### AI/LLM
- [Gemini API Docs](https://ai.google.dev/docs)
- [OpenRouter Docs](https://openrouter.ai/docs)

### Tools
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Redis Docs](https://redis.io/docs/)

---

## 📞 Support

**For technical questions:**
1. Search this documentation
2. Check troubleshooting guides
3. Review known issues
4. Contact development team

**For documentation issues:**
1. Check if information is outdated
2. Verify links and examples
3. Submit documentation update
4. Update this index

---

**Documentation Index Maintained By:** OpenCode  
**Last Updated:** 2026-04-27T09:12:00Z  
**Next Review:** 2026-05-27

