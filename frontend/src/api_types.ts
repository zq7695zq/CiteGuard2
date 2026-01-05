/**
 * Core interfaces for CiteGuard multi-phase visualization
 */

export interface PhaseInfo {
    name: string;
    total: number;
    completed: number;
}

export interface PhaseData {
    status: 'pending' | 'processing' | 'completed' | 'failed' | 'canceled' | 'skipped';
    result_status: string | null;
    logs: string[];
    // Phase 1 specific
    is_verified?: boolean | null;
    verification_message?: string | null;
    paper_abstract?: string | null;
    // Phase 2 specific
    context_matches?: ContextMatch[] | null;
    // Phase 3 specific
    original_bib?: string | null;
    corrected_bib?: string | null;
    bib_changes?: string[] | null;
}

export interface Paper {
    citation_key: string;
    title: string | null;
    phases: {
        "1"?: PhaseData;
        "2"?: PhaseData;
        "3"?: PhaseData;
    };
}

export interface ContextMatch {
    context: string;
    line_number: number;
    section: string;
    is_match: boolean;
    confidence: number;
    explanation: string;
    suggestion: string | null;
}

export interface TaskStatus {
    id: string;
    status: string;
    current_phase: 1 | 2 | 3;
    phases: {
        "1": PhaseInfo;
        "2": PhaseInfo;
        "3": PhaseInfo;
    };
    total: number;
    completed: number;
    progress: number;
}

export interface TaskDetails {
    task_id: string;
    papers: Paper[];
    outputs?: {
        corrected_bib: boolean;
        verification_report: boolean;
        context_report: boolean;
    };
}

// Legacy Job interface for backward compatibility
export interface Job {
    citation_key: string;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    result_status: 'verified' | 'fake' | 'context_mismatch' | null;
    title: string | null;
    verification_message: string | null;
    is_verified: boolean;
    logs: string[];
    context_matches: ContextMatch[];
}
