import React, { useEffect, useState } from 'react';
import axios from 'axios';
import type { TaskStatus, Paper, PhaseData, ContextMatch } from '../api_types';
import {
    CheckCircle, XCircle, AlertTriangle, Loader2, ArrowLeft,
    Play, Pause, Square, SkipForward, Download, FileText,
    Search, MessageSquare, Edit3, ChevronDown, ChevronRight
} from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface DashboardProps {
    taskId: string;
    onReset: () => void;
}

const PHASE_NAMES = {
    1: "Paper Verification",
    2: "Context Matching",
    3: "BIB Correction"
};

const PHASE_ICONS = {
    1: Search,
    2: MessageSquare,
    3: Edit3
};

export const Dashboard: React.FC<DashboardProps> = ({ taskId, onReset }) => {
    const [status, setStatus] = useState<TaskStatus | null>(null);
    const [papers, setPapers] = useState<Paper[]>([]);
    const [hasOutputs, setHasOutputs] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // SSE Connection
    useEffect(() => {
        if (!taskId) return;
        if (status?.status === 'paused') return;

        console.log("Connecting to SSE stream for task:", taskId);
        const eventSource = new EventSource(`http://localhost:8000/api/v1/status/${taskId}/stream`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                setStatus({
                    id: taskId,
                    status: data.task_status,
                    current_phase: data.current_phase,
                    phases: data.phases,
                    total: data.total,
                    completed: data.completed,
                    progress: data.total > 0 ? (data.completed / data.total * 100) : 0
                });

                setPapers(data.papers || []);
                setHasOutputs(data.outputs?.corrected_bib || false);

            } catch (error) {
                console.error("Error parsing SSE data", error);
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE connection error", err);
            eventSource.close();
        };

        return () => {
            eventSource.close();
        };
    }, [taskId, status?.status]);

    const handlePause = async () => {
        try {
            await axios.post(`http://localhost:8000/api/v1/control/${taskId}/pause`);
            setStatus(prev => prev ? { ...prev, status: 'paused' } : null);
        } catch (e) {
            console.error('Failed to pause:', e);
        }
    };

    const handleResume = async () => {
        try {
            await axios.post(`http://localhost:8000/api/v1/control/${taskId}/resume`);
            setStatus(prev => prev ? { ...prev, status: 'processing' } : null);
        } catch (e) {
            console.error('Failed to resume:', e);
        }
    };

    const handleStop = async () => {
        try {
            await axios.post(`http://localhost:8000/api/v1/control/${taskId}/stop`);
            setStatus(prev => prev ? { ...prev, status: 'stopped' } : null);
        } catch (e) {
            console.error('Failed to stop:', e);
        }
    };

    const handleSkipPhase = async () => {
        try {
            await axios.post(`http://localhost:8000/api/v1/control/${taskId}/skip-phase`);
        } catch (e) {
            console.error('Failed to skip phase:', e);
        }
    };

    const handleDownloadBib = () => {
        window.open(`http://localhost:8000/api/v1/control/${taskId}/download/bib`, '_blank');
    };

    if (error) {
        return (
            <div className="flex flex-col justify-center items-center py-20 bg-white rounded-xl shadow-sm">
                <AlertTriangle className="h-12 w-12 text-red-500 mb-4" />
                <h3 className="text-lg font-bold text-gray-900 mb-2">Error Loading Task</h3>
                <p className="text-gray-600 mb-6">{error}</p>
                <button
                    onClick={onReset}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                    Create New Task
                </button>
            </div>
        );
    }

    if (!status) {
        return (
            <div className="flex flex-col justify-center items-center py-20">
                <div className="text-center">
                    <Loader2 className="h-10 w-10 animate-spin text-blue-500 mx-auto mb-4" />
                    <p className="text-gray-500 mb-4">Connecting to task stream...</p>
                    <button onClick={onReset} className="text-sm text-gray-400 hover:text-gray-600 underline">
                        Cancel & New Task
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header / Controls */}
            <div className="flex justify-between items-center bg-white p-6 rounded-xl shadow-sm">
                <div>
                    <button onClick={onReset} className="flex items-center text-sm text-gray-500 hover:text-gray-700 mb-2">
                        <ArrowLeft className="h-4 w-4 mr-1" /> New Task
                    </button>
                    <h2 className="text-xl font-bold flex items-center gap-2">
                        Task: <span className="font-mono text-base font-normal text-gray-600">{taskId.slice(0, 8)}...</span>
                    </h2>
                    <div className="mt-2 flex items-center gap-2">
                        <span className={cn(
                            "px-2 py-1 rounded-full text-xs font-medium capitalize",
                            status.status === 'completed' ? "bg-green-100 text-green-700" :
                                status.status === 'processing' ? "bg-blue-100 text-blue-700" :
                                    status.status === 'paused' ? "bg-yellow-100 text-yellow-700" :
                                        status.status === 'stopped' ? "bg-red-100 text-red-700" :
                                            "bg-gray-100 text-gray-700"
                        )}>
                            {status.status}
                        </span>
                    </div>
                </div>

                <div className="flex gap-2">
                    {status.status === 'processing' && (
                        <>
                            <button
                                onClick={handleSkipPhase}
                                disabled={status.current_phase >= 3}
                                className="flex items-center gap-1 px-3 py-2 bg-gray-50 text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-50"
                                title="Skip current phase"
                            >
                                <SkipForward className="h-4 w-4" />
                            </button>
                            <button
                                onClick={handlePause}
                                className="flex items-center gap-1 px-4 py-2 bg-yellow-50 text-yellow-600 rounded-lg hover:bg-yellow-100"
                            >
                                <Pause className="h-4 w-4" /> Pause
                            </button>
                            <button
                                onClick={handleStop}
                                className="flex items-center gap-1 px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
                            >
                                <Square className="h-4 w-4" /> Stop
                            </button>
                        </>
                    )}
                    {status.status === 'paused' && (
                        <>
                            <button
                                onClick={handleResume}
                                className="flex items-center gap-1 px-4 py-2 bg-green-50 text-green-600 rounded-lg hover:bg-green-100"
                            >
                                <Play className="h-4 w-4" /> Resume
                            </button>
                            <button
                                onClick={handleStop}
                                className="flex items-center gap-1 px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100"
                            >
                                <Square className="h-4 w-4" /> Stop
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Phase Stepper */}
            <div className="bg-white p-6 rounded-xl shadow-sm">
                <div className="flex items-center justify-between">
                    {[1, 2, 3].map((phase) => {
                        const PhaseIcon = PHASE_ICONS[phase as 1 | 2 | 3];
                        const phaseInfo = status.phases[phase.toString() as "1" | "2" | "3"];
                        const isActive = status.current_phase === phase;
                        const isComplete = phaseInfo.completed >= phaseInfo.total && phaseInfo.total > 0;
                        const isPast = status.current_phase > phase;

                        return (
                            <React.Fragment key={phase}>
                                <div className={cn(
                                    "flex flex-col items-center flex-1",
                                    isActive ? "opacity-100" : isPast ? "opacity-70" : "opacity-40"
                                )}>
                                    <div className={cn(
                                        "w-12 h-12 rounded-full flex items-center justify-center mb-2",
                                        isComplete || isPast ? "bg-green-100 text-green-600" :
                                            isActive ? "bg-blue-100 text-blue-600" :
                                                "bg-gray-100 text-gray-400"
                                    )}>
                                        {isComplete || isPast ? (
                                            <CheckCircle className="h-6 w-6" />
                                        ) : (
                                            <PhaseIcon className="h-6 w-6" />
                                        )}
                                    </div>
                                    <span className="text-sm font-medium text-gray-700">
                                        {PHASE_NAMES[phase as 1 | 2 | 3]}
                                    </span>
                                    <span className="text-xs text-gray-500">
                                        {phaseInfo.completed}/{phaseInfo.total}
                                    </span>
                                </div>
                                {phase < 3 && (
                                    <div className={cn(
                                        "h-0.5 flex-1 mx-4",
                                        isPast ? "bg-green-300" : "bg-gray-200"
                                    )} />
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>

                {/* Current Phase Progress */}
                <div className="mt-6">
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">
                            Phase {status.current_phase}: {PHASE_NAMES[status.current_phase]}
                        </span>
                        <span className="text-gray-500">
                            {status.phases[status.current_phase.toString() as "1" | "2" | "3"].completed}/
                            {status.phases[status.current_phase.toString() as "1" | "2" | "3"].total}
                        </span>
                    </div>
                    <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
                        <motion.div
                            className="h-full bg-blue-500"
                            initial={{ width: 0 }}
                            animate={{
                                width: `${(status.phases[status.current_phase.toString() as "1" | "2" | "3"].completed /
                                    Math.max(status.phases[status.current_phase.toString() as "1" | "2" | "3"].total, 1)) * 100}%`
                            }}
                            transition={{ duration: 0.5 }}
                        />
                    </div>
                </div>
            </div>

            {/* Papers List */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-900">Papers ({papers.length})</h3>
                </div>
                <div className="divide-y divide-gray-100">
                    <AnimatePresence>
                        {papers.map((paper) => (
                            <PaperCard key={paper.citation_key} paper={paper} currentPhase={status.current_phase} />
                        ))}
                    </AnimatePresence>
                </div>
            </div>

            {/* Outputs (when completed) */}
            {status.status === 'completed' && hasOutputs && (
                <div className="bg-white p-6 rounded-xl shadow-sm">
                    <h3 className="font-semibold text-gray-900 mb-4">📦 Final Outputs</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <button
                            onClick={handleDownloadBib}
                            className="flex items-center gap-2 px-4 py-3 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-colors"
                        >
                            <Download className="h-5 w-5" />
                            <div className="text-left">
                                <div className="font-medium">Corrected BIB</div>
                                <div className="text-xs text-blue-500">Download .bib file</div>
                            </div>
                        </button>
                        <button
                            onClick={() => window.open(`http://localhost:8000/api/v1/control/${taskId}/download/verification-report`, '_blank')}
                            className="flex items-center gap-2 px-4 py-3 bg-green-50 text-green-600 rounded-lg hover:bg-green-100 transition-colors"
                        >
                            <FileText className="h-5 w-5" />
                            <div className="text-left">
                                <div className="font-medium">Verification Report</div>
                                <div className="text-xs text-green-500">Paper authenticity (.md)</div>
                            </div>
                        </button>
                        <button
                            onClick={() => window.open(`http://localhost:8000/api/v1/control/${taskId}/download/context-report`, '_blank')}
                            className="flex items-center gap-2 px-4 py-3 bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100 transition-colors"
                        >
                            <MessageSquare className="h-5 w-5" />
                            <div className="text-left">
                                <div className="font-medium">Context Report</div>
                                <div className="text-xs text-purple-500">Citation matching (.md)</div>
                            </div>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

// Paper Card Component
const PaperCard: React.FC<{ paper: Paper; currentPhase: number }> = ({ paper, currentPhase }) => {
    const [expanded, setExpanded] = useState(false);

    // Auto-expand if any phase is processing
    useEffect(() => {
        const isProcessing = Object.values(paper.phases).some(p => p?.status === 'processing');
        if (isProcessing) setExpanded(true);
    }, [paper.phases]);

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-4 hover:bg-gray-50/50 transition-colors"
        >
            {/* Header */}
            <div
                className="flex items-start gap-3 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="mt-1">
                    {expanded ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />}
                </div>
                <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-gray-900">{paper.citation_key}</h4>
                    <p className="text-sm text-gray-600 truncate">{paper.title || "Pending..."}</p>
                </div>
                {/* Phase Status Icons */}
                <div className="flex gap-2">
                    {[1, 2, 3].map((phase) => (
                        <PhaseStatusBadge
                            key={phase}
                            phase={phase}
                            data={paper.phases[phase.toString() as "1" | "2" | "3"]}
                            isCurrent={currentPhase === phase}
                        />
                    ))}
                </div>
            </div>

            {/* Expanded Details */}
            {expanded && (
                <div className="mt-4 ml-7 space-y-4">
                    {[1, 2, 3].map((phase) => {
                        const data = paper.phases[phase.toString() as "1" | "2" | "3"];
                        if (!data) return null;
                        return (
                            <PhaseDetail
                                key={phase}
                                phase={phase}
                                data={data}
                                isCurrent={currentPhase === phase}
                            />
                        );
                    })}
                </div>
            )}
        </motion.div>
    );
};

// Phase Status Badge
const PhaseStatusBadge: React.FC<{ phase: number; data?: PhaseData; isCurrent: boolean }> = ({
    phase, data, isCurrent
}) => {
    if (!data) {
        return (
            <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center">
                <span className="text-xs text-gray-400">{phase}</span>
            </div>
        );
    }

    const getStatusStyle = () => {
        switch (data.status) {
            case 'completed':
                if (data.result_status === 'fake' || data.result_status === 'context_mismatch') {
                    return 'bg-red-100 text-red-600';
                }
                return 'bg-green-100 text-green-600';
            case 'processing':
                return 'bg-blue-100 text-blue-600';
            case 'failed':
                return 'bg-red-100 text-red-600';
            case 'skipped':
            case 'canceled':
                return 'bg-gray-100 text-gray-400';
            default:
                return isCurrent ? 'bg-yellow-100 text-yellow-600' : 'bg-gray-100 text-gray-400';
        }
    };

    const getStatusIcon = () => {
        switch (data.status) {
            case 'completed':
                if (data.result_status === 'fake') return <XCircle className="h-3 w-3" />;
                if (data.result_status === 'context_mismatch') return <AlertTriangle className="h-3 w-3" />;
                return <CheckCircle className="h-3 w-3" />;
            case 'processing':
                return <Loader2 className="h-3 w-3 animate-spin" />;
            case 'failed':
                return <XCircle className="h-3 w-3" />;
            default:
                return <span className="text-xs">{phase}</span>;
        }
    };

    return (
        <div className={cn("w-6 h-6 rounded-full flex items-center justify-center", getStatusStyle())}>
            {getStatusIcon()}
        </div>
    );
};

// Phase Detail View
const PhaseDetail: React.FC<{ phase: number; data: PhaseData; isCurrent: boolean }> = ({
    phase, data, isCurrent
}) => {
    const PhaseIcon = PHASE_ICONS[phase as 1 | 2 | 3];

    return (
        <div className={cn(
            "p-3 rounded-lg border",
            data.status === 'processing' ? "border-blue-200 bg-blue-50/50" :
                data.status === 'completed' ? "border-green-200 bg-green-50/30" :
                    data.status === 'failed' ? "border-red-200 bg-red-50/30" :
                        "border-gray-200 bg-gray-50/30"
        )}>
            <div className="flex items-center gap-2 mb-2">
                <PhaseIcon className="h-4 w-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">
                    Phase {phase}: {PHASE_NAMES[phase as 1 | 2 | 3]}
                </span>
                <span className={cn(
                    "text-xs px-1.5 py-0.5 rounded capitalize",
                    data.status === 'completed' ? "bg-green-100 text-green-700" :
                        data.status === 'processing' ? "bg-blue-100 text-blue-700" :
                            data.status === 'failed' ? "bg-red-100 text-red-700" :
                                "bg-gray-100 text-gray-600"
                )}>
                    {data.result_status || data.status}
                </span>
            </div>

            {/* Phase 1: Verification Details */}
            {phase === 1 && data.verification_message && (
                <p className="text-sm text-gray-600 mb-2">{data.verification_message}</p>
            )}
            {phase === 1 && data.paper_abstract && (
                <details className="text-xs">
                    <summary className="text-gray-500 cursor-pointer">Abstract</summary>
                    <p className="mt-1 text-gray-600 italic">{data.paper_abstract}</p>
                </details>
            )}

            {/* Phase 2: Context Matches */}
            {phase === 2 && data.context_matches && data.context_matches.length > 0 && (
                <div className="space-y-2">
                    {data.context_matches.map((ctx, idx) => (
                        <div key={idx} className="text-sm p-2 bg-white rounded border border-gray-100">
                            <div className="flex items-center gap-2 mb-1">
                                {ctx.is_match ? (
                                    <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">Match</span>
                                ) : (
                                    <span className="text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">Mismatch</span>
                                )}
                                <span className="text-xs text-gray-400">Line {ctx.line_number}</span>
                            </div>
                            <p className="text-gray-600 text-xs italic border-l-2 border-gray-200 pl-2">
                                "{ctx.context.slice(0, 150)}..."
                            </p>
                            {ctx.explanation && (
                                <p className="text-xs text-gray-500 mt-1">{ctx.explanation}</p>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Phase 3: BIB Changes */}
            {phase === 3 && data.bib_changes && data.bib_changes.length > 0 && (
                <div className="text-sm">
                    <p className="text-gray-600 mb-1">Changes made:</p>
                    <ul className="list-disc list-inside text-xs text-gray-500 space-y-0.5">
                        {data.bib_changes.slice(0, 5).map((change, idx) => (
                            <li key={idx}>{change}</li>
                        ))}
                    </ul>
                </div>
            )}
            {phase === 3 && data.corrected_bib && (
                <details className="text-xs mt-2">
                    <summary className="text-gray-500 cursor-pointer">Corrected BIB</summary>
                    <pre className="mt-1 p-2 bg-gray-800 text-gray-200 rounded text-xs overflow-x-auto">
                        {data.corrected_bib}
                    </pre>
                </details>
            )}

            {/* Logs */}
            {data.logs && data.logs.length > 0 && (
                <details className="mt-2">
                    <summary className="text-xs text-gray-500 cursor-pointer">
                        Logs ({data.logs.length})
                    </summary>
                    <div className="mt-1 bg-gray-900 rounded p-2 font-mono text-xs text-gray-300 max-h-32 overflow-y-auto">
                        {data.logs.map((log, i) => (
                            <div key={i} className="border-b border-gray-800 last:border-0 py-0.5">{log}</div>
                        ))}
                    </div>
                </details>
            )}
        </div>
    );
};
