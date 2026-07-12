import { memo } from "react";

type Candidate = {
  id: string;
  source: string;
  full_name?: string;
  username?: string;
  headline?: string;
  bio?: string;
  location?: string;
  skills?: string[];
  languages?: string[];
  linkedin_url?: string;
  telegram_url?: string;
  email?: string;
  phone?: string;
  gemini_score?: number;
  gemini_reasoning?: string;
  gemini_dimensions?: Record<string, number>;
  red_flags?: string[];
  open_to_work?: boolean;
  embed_similarity?: number;
  scan_depth?: number;
  status?: string;
  educations?: Array<{ school: string; field: string; location: string; start: string; end: string }>;
  positions?: Array<{ title: string; company: string; location: string; start: string; end: string; desc: string }>;
};

type CandidateCardProps = {
  candidate: Candidate;
  isExpanded: boolean;
  onToggle: () => void;
};

export const CandidateCard = memo(({ candidate, isExpanded, onToggle }: CandidateCardProps) => {
  const name = candidate.full_name || candidate.username || "Unknown";
  const score = candidate.gemini_score;
  
  return (
    <div className="border border-[var(--border)] rounded-lg p-4 hover:border-[var(--accent)] transition-colors">
      <div className="flex items-start justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            {score !== undefined && (
              <span className={`text-lg font-bold shrink-0 ${
                score >= 80 ? "text-green-400" : 
                score >= 60 ? "text-yellow-400" : 
                "text-red-400"
              }`}>
                {score}
              </span>
            )}
            <div className="min-w-0">
              <div className="font-medium truncate">{name}</div>
              {candidate.headline && (
                <div className="text-sm text-[var(--muted)] truncate">{candidate.headline}</div>
              )}
            </div>
          </div>
          
          {candidate.location && (
            <div className="text-sm text-[var(--muted)] mt-1 truncate">{candidate.location}</div>
          )}
          
          {candidate.skills && candidate.skills.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {candidate.skills.slice(0, 5).map((skill, i) => (
                <span key={i} className="text-xs bg-[var(--hover)] px-2 py-1 rounded">
                  {skill}
                </span>
              ))}
              {candidate.skills.length > 5 && (
                <span className="text-xs text-[var(--muted)]">+{candidate.skills.length - 5} more</span>
              )}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2 shrink-0 ml-2">
          {candidate.open_to_work && (
            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded whitespace-nowrap">
              Open to work
            </span>
          )}
          <span className="text-[var(--muted)]">{isExpanded ? "▼" : "▶"}</span>
        </div>
      </div>
      
      {isExpanded && (
        <div className="mt-4 space-y-3 text-sm border-t border-[var(--border)] pt-4">
          {candidate.gemini_reasoning && (
            <div>
              <div className="font-medium mb-1">Reasoning</div>
              <div className="text-[var(--muted)]">{candidate.gemini_reasoning}</div>
            </div>
          )}
          
          {candidate.gemini_dimensions && Object.keys(candidate.gemini_dimensions).length > 0 && (
            <div>
              <div className="font-medium mb-1">Dimensions</div>
              <div className="space-y-1">
                {Object.entries(candidate.gemini_dimensions).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-[var(--muted)] capitalize">{key.replace(/_/g, ' ')}</span>
                    <span>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {candidate.red_flags && candidate.red_flags.length > 0 && (
            <div>
              <div className="font-medium mb-1 text-red-400">Red Flags</div>
              <div className="flex flex-wrap gap-1">
                {candidate.red_flags.map((flag, i) => (
                  <span key={i} className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded">
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}
          
          {candidate.bio && (
            <div>
              <div className="font-medium mb-1">Bio</div>
              <div className="text-[var(--muted)] whitespace-pre-wrap line-clamp-6">{candidate.bio}</div>
            </div>
          )}
          
          {candidate.positions && candidate.positions.length > 0 && (
            <div>
              <div className="font-medium mb-1">Experience</div>
              <div className="space-y-2">
                {candidate.positions.slice(0, 3).map((pos, i) => (
                  <div key={i} className="text-[var(--muted)]">
                    <div className="font-medium text-white">{pos.title}</div>
                    <div className="text-sm">{pos.company} • {pos.start} - {pos.end}</div>
                  </div>
                ))}
                {candidate.positions.length > 3 && (
                  <div className="text-xs text-[var(--muted)]">+{candidate.positions.length - 3} more positions</div>
                )}
              </div>
            </div>
          )}
          
          <div className="flex gap-3 pt-2">
            {candidate.linkedin_url && (
              <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" 
                 className="text-blue-400 hover:underline text-sm">
                LinkedIn →
              </a>
            )}
            {candidate.telegram_url && (
              <a href={candidate.telegram_url} target="_blank" rel="noopener noreferrer"
                 className="text-blue-400 hover:underline text-sm">
                Telegram →
              </a>
            )}
            {candidate.email && (
              <a href={`mailto:${candidate.email}`} className="text-blue-400 hover:underline text-sm">
                {candidate.email}
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function for memo
  return (
    prevProps.candidate.id === nextProps.candidate.id &&
    prevProps.isExpanded === nextProps.isExpanded &&
    prevProps.candidate.gemini_score === nextProps.candidate.gemini_score &&
    prevProps.candidate.status === nextProps.candidate.status
  );
});

CandidateCard.displayName = "CandidateCard";
