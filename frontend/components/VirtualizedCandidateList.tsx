import { memo } from "react";
import { List } from "react-window";

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

type VirtualizedCandidateListProps = {
  candidates: Candidate[];
  expandedId: string | null;
  onToggleExpand: (id: string) => void;
  height: number;
};

const CandidateRow = memo(({ 
  candidate, 
  isExpanded, 
  onToggle 
}: { 
  candidate: Candidate; 
  isExpanded: boolean; 
  onToggle: () => void;
}) => {
  const name = candidate.full_name || candidate.username || "Unknown";
  const score = candidate.gemini_score;
  
  return (
    <div className="border-b border-[var(--border)] p-4 hover:bg-[var(--hover)]">
      <div className="flex items-start justify-between cursor-pointer" onClick={onToggle}>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            {score !== undefined && (
              <span className={`text-lg font-bold ${
                score >= 80 ? "text-green-400" : 
                score >= 60 ? "text-yellow-400" : 
                "text-red-400"
              }`}>
                {score}
              </span>
            )}
            <div>
              <div className="font-medium">{name}</div>
              {candidate.headline && (
                <div className="text-sm text-[var(--muted)]">{candidate.headline}</div>
              )}
            </div>
          </div>
          
          {candidate.location && (
            <div className="text-sm text-[var(--muted)] mt-1">{candidate.location}</div>
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
        
        <div className="flex items-center gap-2">
          {candidate.open_to_work && (
            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
              Open to work
            </span>
          )}
          <span className="text-[var(--muted)]">{isExpanded ? "▼" : "▶"}</span>
        </div>
      </div>
      
      {isExpanded && (
        <div className="mt-4 space-y-3 text-sm">
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
                    <span className="text-[var(--muted)]">{key}</span>
                    <span>{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {candidate.bio && (
            <div>
              <div className="font-medium mb-1">Bio</div>
              <div className="text-[var(--muted)] whitespace-pre-wrap">{candidate.bio}</div>
            </div>
          )}
          
          <div className="flex gap-2">
            {candidate.linkedin_url && (
              <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer" 
                 className="text-blue-400 hover:underline">
                LinkedIn
              </a>
            )}
            {candidate.telegram_url && (
              <a href={candidate.telegram_url} target="_blank" rel="noopener noreferrer"
                 className="text-blue-400 hover:underline">
                Telegram
              </a>
            )}
            {candidate.email && (
              <a href={`mailto:${candidate.email}`} className="text-blue-400 hover:underline">
                {candidate.email}
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

CandidateRow.displayName = "CandidateRow";

export function VirtualizedCandidateList({ 
  candidates, 
  expandedId, 
  onToggleExpand,
  height 
}: VirtualizedCandidateListProps) {
  
  return (
    <List
      rowComponent={({ index, style }) => {
        const candidate = candidates[index];
        const isExpanded = expandedId === candidate.id;
        
        return (
          <div style={style}>
            <CandidateRow
              candidate={candidate}
              isExpanded={isExpanded}
              onToggle={() => onToggleExpand(candidate.id)}
            />
          </div>
        );
      }}
      rowCount={candidates.length}
      rowHeight={(index: number) => {
        const candidate = candidates[index];
        const isExpanded = expandedId === candidate.id;
        return isExpanded ? 400 : 120;
      }}
      rowProps={{}}
      defaultHeight={height}
    >
      {null}
    </List>
  );
}
