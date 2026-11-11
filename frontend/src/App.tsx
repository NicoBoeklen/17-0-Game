import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckCircle2,
  ChevronRight,
  Info,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  Trophy,
  X,
} from 'lucide-react';
import {
  DraftPlayer,
  EvaluationResult,
  GameSession,
  RosterSlot,
  RunHistoryEntry,
  UserPick,
} from './types';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '';

const POS_BADGE_COLORS: Record<string, string> = {
  QB: 'bg-[#5c1b23] text-[#fecdd3] border-[#78232d]',
  RB: 'bg-[#124529] text-[#bbf7d0] border-[#185c37]',
  WR: 'bg-[#153168] text-[#bfdbfe] border-[#1e428a]',
  TE: 'bg-[#5c2c13] text-[#fed7aa] border-[#783919]',
  OL: 'bg-[#0f4842] text-[#99f6e4] border-[#145e56]',
  DEF: 'bg-[#3c195c] text-[#e9d5ff] border-[#4e2178]',
  HC: 'bg-[#4f3910] text-[#fef08a] border-[#694c15]',
};

const GRADE_STYLES: Record<string, string> = {
  S: 'bg-gradient-to-r from-amber-400 to-yellow-500 text-black font-black shadow-sm shadow-amber-500/30',
  'A+': 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold',
  A: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold',
  'B+': 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold',
  B: 'bg-sky-500/15 text-sky-400 border border-sky-500/30 font-semibold',
  'C+': 'bg-amber-500/20 text-amber-300 border border-amber-500/40 font-semibold',
  C: 'bg-amber-500/15 text-amber-400 border border-amber-500/30 font-semibold',
  D: 'bg-orange-500/20 text-orange-300 border border-orange-500/40 font-semibold',
  F: 'bg-rose-500/20 text-rose-300 border border-rose-500/40 font-semibold',
};

function getRankBadgeStyle(rank: number): string {
  if (rank === 1) {
    return 'bg-gradient-to-r from-amber-400 to-yellow-500 text-black font-black border border-amber-300';
  }
  if (rank <= 5) {
    return 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-extrabold';
  }
  if (rank <= 12) {
    return 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-bold';
  }
  if (rank <= 24) {
    return 'bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold';
  }
  return 'bg-rose-500/15 text-rose-300 border border-rose-500/30 font-semibold';
}

/**
 * Trademark-safe Team Emblem (renders authentic team primary/secondary colors & city code
 * without external ESPN/NFL copyrighted vector logos).
 */
function TeamBadge({
  abbr,
  color = '#1e293b',
  altColor = '#ffffff',
  size = 'md',
}: {
  abbr: string;
  color?: string;
  altColor?: string;
  size?: 'xs' | 'sm' | 'md' | 'lg';
}) {
  const sizeClasses = {
    xs: 'w-5 h-5 text-[8px] border',
    sm: 'w-7 h-7 text-[10px] border',
    md: 'w-10 h-10 text-xs border-2',
    lg: 'w-14 h-14 sm:w-16 sm:h-16 text-base sm:text-lg border-2',
  }[size];

  return (
    <div
      style={{
        backgroundColor: color,
        borderColor: altColor || '#ffffff',
      }}
      className={`${sizeClasses} rounded-full flex items-center justify-center font-black tracking-tight text-white shadow-inner shrink-0 select-none`}
    >
      <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.85)]">{abbr}</span>
    </div>
  );
}

/**
 * Copyright-safe Player Jersey Avatar (renders jersey number or unit code in team colors
 * instead of external ESPN player headshots).
 */
function PlayerAvatar({
  jersey,
  position,
  color = '#181920',
  altColor = '#3f3f46',
  size = 'md',
}: {
  jersey?: string;
  position: string;
  color?: string;
  altColor?: string;
  size?: 'sm' | 'md' | 'lg';
}) {
  const isUnit = ['OL', 'DEF', 'HC'].includes(position);
  const label = isUnit ? position : jersey ? `#${jersey}` : position;
  const sizeClasses = {
    sm: 'w-9 h-9 text-[11px]',
    md: 'w-10 h-10 text-xs',
    lg: 'w-12 h-12 text-sm',
  }[size];

  return (
    <div
      style={{
        background: `linear-gradient(135deg, ${color} 0%, #101116 100%)`,
        borderColor: altColor || '#2c2e38',
      }}
      className={`${sizeClasses} rounded-full border flex items-center justify-center font-black text-white shrink-0 select-none shadow-sm`}
    >
      <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">{label}</span>
    </div>
  );
}

const STORAGE_KEY_HISTORY = 'nfl_17_0_run_history_v1';

export default function App() {
  const [session, setSession] = useState<GameSession | null>(null);
  const [currentRoundIdx, setCurrentRoundIdx] = useState<number>(0);
  const [picksBySlot, setPicksBySlot] = useState<Record<string, UserPick>>({});
  const [picksByRound, setPicksByRound] = useState<Record<number, UserPick>>({});
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [posFilter, setPosFilter] = useState<string>('ALL');
  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [activeResultTab, setActiveResultTab] = useState<
    'grades' | 'rankings' | 'optimal' | 'schedule'
  >('grades');
  const [leaderboardPos, setLeaderboardPos] = useState<string>('QB');
  const [showInfoModal, setShowInfoModal] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pickerRef = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const [history, setHistory] = useState<RunHistoryEntry[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_HISTORY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const bestRecordEntry = useMemo(() => {
    if (history.length === 0) return null;
    return [...history].sort((a, b) => b.wins - a.wins || b.team_ovr - a.team_ovr)[0];
  }, [history]);

  const perfectCount = useMemo(
    () => history.filter((h) => h.wins === 17).length,
    [history]
  );

  const startNewGame = async () => {
    setLoading(true);
    setErrorMsg(null);
    setEvaluation(null);
    setPicksBySlot({});
    setPicksByRound({});
    setCurrentRoundIdx(0);
    setSearchQuery('');
    setPosFilter('ALL');
    setActiveResultTab('grades');

    try {
      const res = await fetch(`${API_BASE}/api/game/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'ultimate' }),
      });
      if (!res.ok) throw new Error(`Server-Fehler (${res.status})`);
      const data: GameSession = await res.json();
      setSession(data);
    } catch (err: any) {
      setErrorMsg(
        err?.message || 'Verbindung zum Server fehlgeschlagen. Bitte neu laden.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    startNewGame();
  }, []);

  const currentRoundTeam = useMemo(() => {
    if (!session || currentRoundIdx >= session.rounds.length) return null;
    return session.rounds[currentRoundIdx];
  }, [session, currentRoundIdx]);

  const openSlots = useMemo(() => {
    if (!session) return [];
    return session.slots.filter((s) => !picksBySlot[s.slot_id]);
  }, [session, picksBySlot]);

  const getEligibleOpenSlots = (position: string): RosterSlot[] => {
    if (!session) return [];
    const matching = openSlots.filter((s) => s.allowed.includes(position));
    return matching.sort((a, b) => a.allowed.length - b.allowed.length);
  };

  // Count how many slots are still open per position (e.g. RB: 2, WR: 2, TE: 2, QB: 1)
  const openCountByPos = useMemo(() => {
    const counts: Record<string, number> = {
      QB: 0,
      RB: 0,
      WR: 0,
      TE: 0,
      OL: 0,
      DEF: 0,
      HC: 0,
    };
    for (const s of openSlots) {
      for (const allowedPos of s.allowed) {
        counts[allowedPos] = (counts[allowedPos] || 0) + 1;
      }
    }
    return counts;
  }, [openSlots]);

  // Sort & filter current team's players: eligible open-slot starters first!
  const filteredPlayers = useMemo(() => {
    if (!currentRoundTeam) return [];
    const q = searchQuery.trim().toLowerCase();

    const list = currentRoundTeam.players.filter((p) => {
      if (posFilter !== 'ALL' && p.position !== posFilter) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        p.position.toLowerCase().includes(q) ||
        p.depth_label.toLowerCase().includes(q) ||
        (p.college && p.college.toLowerCase().includes(q))
      );
    });

    return [...list].sort((a, b) => {
      const aOpen = getEligibleOpenSlots(a.position).length > 0 ? 1 : 0;
      const bOpen = getEligibleOpenSlots(b.position).length > 0 ? 1 : 0;
      if (aOpen !== bOpen) return bOpen - aOpen;
      const aStarter = a.is_starter ? 1 : 0;
      const bStarter = b.is_starter ? 1 : 0;
      if (aStarter !== bStarter) return bStarter - aStarter;
      return a.depth_order - b.depth_order;
    });
  }, [currentRoundTeam, searchQuery, posFilter, openSlots]);

  const handleSelectPlayer = async (player: DraftPlayer, explicitSlotId?: string) => {
    if (!session || !currentRoundTeam || evaluation) return;

    const eligibleSlots = getEligibleOpenSlots(player.position);
    if (eligibleSlots.length === 0) return;

    const chosenSlot = explicitSlotId
      ? eligibleSlots.find((s) => s.slot_id === explicitSlotId) || eligibleSlots[0]
      : eligibleSlots[0];

    const newPick: UserPick = {
      round: currentRoundTeam.round,
      slot_id: chosenSlot.slot_id,
      player_id: player.id,
      team_abbr: currentRoundTeam.abbr,
      team_color: currentRoundTeam.color,
      team_alt_color: currentRoundTeam.alt_color,
      player,
    };

    const updatedBySlot = { ...picksBySlot, [chosenSlot.slot_id]: newPick };
    const updatedByRound = { ...picksByRound, [currentRoundTeam.round]: newPick };

    setPicksBySlot(updatedBySlot);
    setPicksByRound(updatedByRound);
    setSearchQuery('');
    setPosFilter('ALL');

    const totalPicked = Object.keys(updatedBySlot).length;
    if (totalPicked < session.total_rounds) {
      setCurrentRoundIdx((prev) => prev + 1);
    } else {
      await runEvaluation(session, Object.values(updatedBySlot));
    }
  };

  const runEvaluation = async (activeSession: GameSession, allPicks: UserPick[]) => {
    setEvaluating(true);
    try {
      const res = await fetch(`${API_BASE}/api/game/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'ultimate',
          session_token: activeSession.session_token,
          drawn_teams: activeSession.rounds.map((r) => r.abbr),
          picks: allPicks.map((p) => ({
            round: p.round,
            slot_id: p.slot_id,
            player_id: p.player_id,
            team_abbr: p.team_abbr,
          })),
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        throw new Error(payload?.error || `Auswertungs-Fehler (${res.status})`);
      }
      const result: EvaluationResult = payload;
      setEvaluation(result);

      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 150);

      const entry: RunHistoryEntry = {
        id: `${Date.now()}`,
        timestamp: new Date().toISOString(),
        mode: 'ultimate',
        record: result.record,
        wins: result.wins,
        losses: result.losses,
        team_ovr: result.team_ovr,
        team_grade: result.team_grade,
      };
      const updatedHistory = [entry, ...history].slice(0, 50);
      setHistory(updatedHistory);
      try {
        localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(updatedHistory));
      } catch {
        // ignore storage quota errors
      }
    } catch (err: any) {
      setErrorMsg(err?.message || 'Fehler bei der Team-Berechnung.');
    } finally {
      setEvaluating(false);
    }
  };

  const evaluatedPickMap = useMemo(() => {
    if (!evaluation) return {};
    const map: Record<string, EvaluationResult['picks'][0]> = {};
    for (const ep of evaluation.picks) {
      map[ep.slot_id] = ep;
    }
    return map;
  }, [evaluation]);

  const draftedPlayerIds = useMemo(() => {
    return new Set(Object.values(picksBySlot).map((p) => p.player_id));
  }, [picksBySlot]);

  const filledCount = Object.keys(picksBySlot).length;
  const totalSlots = session?.total_rounds || 10;

  return (
    <div className="min-h-screen bg-[#060607] text-zinc-100 pb-16 selection:bg-orange-500/30 selection:text-orange-200 flex flex-col justify-between">
      <div className="max-w-[1020px] w-full mx-auto px-3.5 sm:px-6 pt-5 sm:pt-8">
        {/* Compact Responsive Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-[#191a20]">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-2xl sm:text-[30px] font-extrabold tracking-tight text-white leading-tight">
                Build A 17-0 Team
              </h1>
              <span className="px-2.5 py-0.5 rounded-full bg-orange-500/15 border border-orange-500/30 text-orange-300 text-xs font-extrabold uppercase tracking-wider">
                Ultimate 10-Slot
              </span>
            </div>
            <p className="text-[#9ca3af] text-xs sm:text-sm mt-1">
              Spin 10 random football teams & draft the undefeated 2026/27 roster
            </p>
          </div>

          <div className="flex items-center justify-between sm:justify-end gap-3">
            <div className="flex items-center gap-2.5 text-xs sm:text-sm text-[#9ca3af] bg-[#0f1014] border border-[#22232a] px-3 py-1.5 rounded-xl">
              <button
                onClick={() => setShowInfoModal(true)}
                title="Spielregeln & OL-Bewertung"
                className="text-zinc-400 hover:text-white transition"
              >
                <Info className="w-4 h-4" />
              </button>
              <span>
                Best:{' '}
                <strong className="text-white font-bold">
                  {bestRecordEntry ? bestRecordEntry.record : '—'}
                </strong>
              </span>
              {perfectCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-[11px] font-bold">
                  <Trophy className="w-3 h-3" /> {perfectCount}× 17-0
                </span>
              )}
            </div>

            <button
              onClick={() => startNewGame()}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs sm:text-sm font-extrabold transition active:scale-[0.98] shrink-0"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>New Game</span>
            </button>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-5 p-3.5 rounded-xl bg-rose-950/50 border border-rose-700/60 text-rose-200 flex items-center justify-between gap-3">
            <div className="text-xs sm:text-sm">
              <strong>Hinweis:</strong> {errorMsg}
            </div>
            <button
              onClick={() => startNewGame()}
              className="px-3 py-1 rounded-lg bg-rose-800/60 hover:bg-rose-700/60 text-xs font-semibold shrink-0"
            >
              Neu starten
            </button>
          </div>
        )}

        {/* Main Responsive Two-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-7 items-start">
          {/* LEFT COLUMN: STEP 1 (TEAM) & STEP 2 (PLAYER PICKER) */}
          <div className="lg:col-span-5 space-y-4 sm:space-y-5">
            {/* STEP 1: RANDOM TEAM */}
            <div className="bg-[#0b0b0d] border border-[#1f2025] rounded-2xl p-4 sm:p-5 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold tracking-wider text-[#a1a1aa] uppercase">
                  STEP 1: RANDOM TEAM
                </h2>
                {session && !evaluation && (
                  <span className="text-xs font-bold text-zinc-400">
                    Round {Math.min(currentRoundIdx + 1, session.total_rounds)}/
                    {session.total_rounds}
                  </span>
                )}
              </div>

              {loading || !session ? (
                <div className="py-6 flex flex-col items-center justify-center gap-2.5 text-zinc-500">
                  <RefreshCw className="w-5 h-5 animate-spin text-zinc-400" />
                  <span className="text-xs">Loading 2026/27 teams...</span>
                </div>
              ) : (
                <>
                  {currentRoundTeam && !evaluation ? (
                    <div className="flex items-center gap-3.5 mb-4">
                      <TeamBadge
                        abbr={currentRoundTeam.abbr}
                        color={currentRoundTeam.color}
                        altColor={currentRoundTeam.alt_color}
                        size="lg"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="px-2.5 py-0.5 rounded-full bg-[#e5e7eb] text-[#09090b] text-[11px] font-extrabold tracking-tight">
                            Your pick!
                          </span>
                          {currentRoundTeam.record_2026 && (
                            <span className="text-xs text-zinc-400 font-medium">
                              2026 Record: {currentRoundTeam.record_2026}
                            </span>
                          )}
                        </div>
                        <h3 className="text-lg sm:text-xl font-extrabold text-white truncate">
                          {currentRoundTeam.name}
                        </h3>
                      </div>
                    </div>
                  ) : evaluation ? (
                    <div className="flex items-center gap-3.5 mb-4 p-3 rounded-xl bg-[#111216] border border-[#23252c]">
                      <div className="w-12 h-12 rounded-full bg-amber-500/15 border border-amber-400/30 flex items-center justify-center shrink-0">
                        <Trophy className="w-5 h-5 text-amber-400" />
                      </div>
                      <div>
                        <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                          Draft Complete ({session.total_rounds}/{session.total_rounds})
                        </div>
                        <div className="text-base sm:text-lg font-extrabold text-white">
                          Record: {evaluation.record} ({evaluation.team_ovr} OVR)
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {/* 10 Round Circles */}
                  <div className="grid grid-cols-5 sm:flex sm:flex-wrap items-center gap-2">
                    {session.rounds.map((r, idx) => {
                      const pickedInRound = picksByRound[r.round];
                      const isCurrent = idx === currentRoundIdx && !evaluation;
                      const isRevealed = idx <= currentRoundIdx || Boolean(evaluation);

                      return (
                        <div
                          key={r.round}
                          title={
                            pickedInRound
                              ? `Round ${r.round} (${r.abbr}): ${pickedInRound.player.name} (${pickedInRound.slot_id})`
                              : isCurrent
                              ? `Round ${r.round}: ${r.name}`
                              : `Round ${r.round}`
                          }
                          className={`h-9 sm:w-10 sm:h-10 rounded-xl sm:rounded-full flex items-center justify-center text-xs font-bold transition-all select-none ${
                            isCurrent
                              ? 'ring-2 ring-white bg-[#181920]'
                              : pickedInRound
                              ? 'opacity-90'
                              : 'bg-[#0d0e11] border border-dashed border-[#24262d] text-[#71717a]'
                          }`}
                        >
                          {isRevealed ? (
                            <TeamBadge
                              abbr={r.abbr}
                              color={r.color}
                              altColor={r.alt_color}
                              size="sm"
                            />
                          ) : (
                            <span>{r.round}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            {/* STEP 2: PICK YOUR PLAYER (Mobile & Laptop optimized, always visible!) */}
            <div
              ref={pickerRef}
              className="bg-[#0b0b0d] border border-[#1f2025] rounded-2xl p-4 sm:p-5 shadow-xl"
            >
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold tracking-wider text-[#a1a1aa] uppercase">
                  STEP 2: PICK YOUR PLAYER
                </h2>
                {!evaluation && (
                  <span className="text-[11px] text-zinc-400">
                    {openSlots.length} {openSlots.length === 1 ? 'slot' : 'slots'} left
                  </span>
                )}
              </div>

              {!evaluation && currentRoundTeam ? (
                <>
                  {/* Open Position Filter Pills (shows live remaining slot count!) */}
                  <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-3 no-scrollbar">
                    <button
                      onClick={() => setPosFilter('ALL')}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-bold shrink-0 transition ${
                        posFilter === 'ALL'
                          ? 'bg-white text-black'
                          : 'bg-[#14151a] text-zinc-300 hover:text-white border border-[#252730]'
                      }`}
                    >
                      All
                    </button>
                    {(['QB', 'RB', 'WR', 'TE', 'OL', 'DEF', 'HC'] as const).map((pos) => {
                      const openCount = openCountByPos[pos] || 0;
                      const isSelected = posFilter === pos;
                      return (
                        <button
                          key={pos}
                          onClick={() => setPosFilter(isSelected ? 'ALL' : pos)}
                          className={`px-2.5 py-1.5 rounded-lg text-xs font-bold shrink-0 transition flex items-center gap-1 ${
                            isSelected
                              ? 'bg-white text-black'
                              : openCount > 0
                              ? 'bg-[#14151a] text-zinc-200 hover:bg-[#1c1e26] border border-[#252730]'
                              : 'bg-[#0c0d10] text-zinc-600 border border-[#18191e] line-through'
                          }`}
                        >
                          <span>{pos}</span>
                          {openCount > 1 && (
                            <span
                              className={`text-[10px] px-1 rounded ${
                                isSelected
                                  ? 'bg-black/20 text-black'
                                  : 'bg-zinc-800 text-zinc-300'
                              }`}
                            >
                              {openCount}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  {/* Compact Search Input */}
                  <div className="relative mb-3">
                    <Search className="w-4 h-4 text-[#9ca3af] absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder={`Search ${currentRoundTeam.abbr} players or position...`}
                      className="w-full bg-[#131418] border border-[#2c2e36] focus:border-[#4b4e5c] rounded-xl pl-10 pr-8 py-2.5 text-sm text-white placeholder:text-[#71717a] focus:outline-none transition"
                    />
                    {searchQuery && (
                      <button
                        onClick={() => setSearchQuery('')}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Always-Visible Scrollable Player Cards */}
                  <div className="space-y-1.5 max-h-[360px] sm:max-h-[410px] overflow-y-auto pr-1">
                    {filteredPlayers.length === 0 ? (
                      <div className="py-6 text-center text-xs text-zinc-500 bg-[#111216] rounded-xl border border-[#1f2025]">
                        No matching players found on {currentRoundTeam.abbr}.
                      </div>
                    ) : (
                      filteredPlayers.map((player) => {
                        const eligibleSlots = getEligibleOpenSlots(player.position);
                        const isSelectable = eligibleSlots.length > 0;
                        const badgeClass =
                          POS_BADGE_COLORS[player.position] ||
                          'bg-zinc-800 text-zinc-300 border-zinc-700';

                        return (
                          <div
                            key={player.id}
                            onClick={() => isSelectable && handleSelectPlayer(player)}
                            className={`group flex items-center justify-between gap-2.5 p-2.5 rounded-xl border transition-all ${
                              isSelectable
                                ? 'bg-[#121318] hover:bg-[#181a22] active:scale-[0.99] border-[#22242c] hover:border-[#383b47] cursor-pointer'
                                : 'bg-[#0c0d10] border-[#18191e] opacity-40 cursor-not-allowed'
                            }`}
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <span
                                className={`w-9 text-center py-1 rounded-md text-[11px] font-bold border shrink-0 ${badgeClass}`}
                              >
                                {player.position}
                              </span>

                              <PlayerAvatar
                                jersey={player.jersey}
                                position={player.position}
                                color={currentRoundTeam.color}
                                altColor={currentRoundTeam.alt_color}
                                size="sm"
                              />

                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-xs sm:text-[13.5px] font-semibold text-zinc-100 group-hover:text-white truncate">
                                    {player.name}
                                  </span>
                                  {player.is_starter && (
                                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shrink-0">
                                      {player.depth_label}
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-zinc-500 truncate">
                                  {['OL', 'DEF', 'HC'].includes(player.position)
                                    ? `${currentRoundTeam.name} Unit`
                                    : [
                                        player.jersey ? `#${player.jersey}` : null,
                                        player.college || null,
                                      ]
                                        .filter(Boolean)
                                        .join(' • ')}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-1 shrink-0">
                              {!isSelectable ? (
                                <span className="text-[11px] font-medium text-zinc-600 px-1.5">
                                  Filled
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-0.5 px-2.5 py-1.5 rounded-lg bg-[#191b22] group-hover:bg-white group-hover:text-black text-zinc-200 text-xs font-extrabold border border-[#2c2f3b] transition">
                                  <span>+{eligibleSlots[0].slot_id}</span>
                                  <ChevronRight className="w-3.5 h-3.5" />
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </>
              ) : evaluation ? (
                <div className="space-y-3">
                  <div className="p-3.5 rounded-xl bg-[#111216] border border-[#22242c] text-xs sm:text-sm text-zinc-300 leading-relaxed">
                    {evaluation.summary_de}
                    {evaluation.bottleneck_note && (
                      <div className="mt-2 text-xs text-amber-300 font-medium">
                        ⚠️ {evaluation.bottleneck_note}
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      onClick={() => {
                        setActiveResultTab('rankings');
                        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
                      }}
                      className="p-3 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-left transition"
                    >
                      <div className="text-[10px] font-bold uppercase text-amber-300">
                        League Rankings
                      </div>
                      <div className="text-xs font-bold text-white mt-0.5">
                        🏆 Position Ranks (#1–#32) →
                      </div>
                    </button>
                    <button
                      onClick={() => {
                        setActiveResultTab('optimal');
                        resultsRef.current?.scrollIntoView({ behavior: 'smooth' });
                      }}
                      className="p-3 rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 text-left transition"
                    >
                      <div className="text-[10px] font-bold uppercase text-indigo-300">
                        Best Possible
                      </div>
                      <div className="text-xs font-bold text-white mt-0.5">
                        🧠 Optimal: {evaluation.optimal_analysis?.optimal_record} →
                      </div>
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          {/* RIGHT COLUMN: YOUR 10-SLOT ULTIMATE ROSTER */}
          <div className="lg:col-span-7">
            <div className="bg-[#0b0b0d] border border-[#1f2025] rounded-2xl p-4 sm:p-6 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold tracking-wider text-[#a1a1aa] uppercase">
                  YOUR ULTIMATE ROSTER (10 SLOTS)
                </h2>
                <div className="flex items-center gap-2.5">
                  {evaluation && (
                    <span className="px-2.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-extrabold">
                      OVR: {evaluation.team_ovr} ({evaluation.team_grade})
                    </span>
                  )}
                  <span className="text-xs font-bold text-[#9ca3af]">
                    {filledCount}/{totalSlots}
                  </span>
                </div>
              </div>

              <div className="divide-y divide-[#18191e]">
                {(session?.slots || []).map((slot) => {
                  const pick = picksBySlot[slot.slot_id];
                  const evalItem = evaluatedPickMap[slot.slot_id];
                  const badgeClass =
                    POS_BADGE_COLORS[slot.label] ||
                    POS_BADGE_COLORS[slot.slot_id] ||
                    'bg-zinc-800 text-zinc-300 border-zinc-700';

                  return (
                    <div
                      key={slot.slot_id}
                      onClick={() => {
                        if (!pick && !evaluation) {
                          setPosFilter(slot.label);
                          pickerRef.current?.scrollIntoView({
                            behavior: 'smooth',
                            block: 'nearest',
                          });
                        }
                      }}
                      className={`py-3 px-1 flex items-center justify-between gap-2.5 transition ${
                        !pick && !evaluation
                          ? 'hover:bg-[#111216] cursor-pointer rounded-lg'
                          : ''
                      }`}
                    >
                      <div className="flex items-center gap-2.5 sm:gap-3.5 min-w-0">
                        <span
                          className={`w-11 text-center py-1 rounded-md text-[11px] sm:text-xs font-bold border shrink-0 ${badgeClass}`}
                        >
                          {slot.slot_id}
                        </span>

                        {!pick ? (
                          <div className="flex items-center gap-2.5">
                            <div className="w-9 h-9 rounded-full bg-[#121317] border border-[#22242a] flex items-center justify-center">
                              <div className="w-2 h-2 rounded-full bg-[#3f414a]" />
                            </div>
                            <span className="text-sm font-medium text-[#71717a]">
                              Open — tap to filter {slot.label}
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
                            <div className="relative shrink-0">
                              <PlayerAvatar
                                jersey={pick.player.jersey}
                                position={pick.player.position}
                                color={pick.team_color}
                                altColor={pick.team_alt_color}
                                size="sm"
                              />
                              <div className="absolute -bottom-1 -right-1">
                                <TeamBadge
                                  abbr={pick.team_abbr}
                                  color={pick.team_color}
                                  altColor={pick.team_alt_color}
                                  size="xs"
                                />
                              </div>
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                                <span className="text-sm sm:text-[15px] font-semibold text-white truncate">
                                  {pick.player.name}
                                </span>
                                <span className="text-[11px] font-bold text-zinc-400">
                                  {pick.team_abbr}
                                </span>
                                {evalItem && (
                                  <span
                                    className={`px-1.5 py-0.5 rounded text-[10px] sm:text-[11px] tracking-tight ${getRankBadgeStyle(
                                      evalItem.player.pos_rank
                                    )}`}
                                  >
                                    #{evalItem.player.pos_rank} {evalItem.player.position}
                                  </span>
                                )}
                              </div>
                              {evalItem && (
                                <div className="hidden sm:block text-[11px] text-zinc-400 truncate mt-0.5">
                                  {evalItem.player.stat_line}
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Right side: Position Rank + OVR + Grade */}
                      <div className="flex items-center gap-2 shrink-0">
                        {evalItem ? (
                          <div className="flex items-center gap-2">
                            <div className="text-right">
                              <div className="hidden sm:block text-[10px] text-zinc-400 font-bold uppercase">
                                #{evalItem.player.pos_rank} {evalItem.player.position}
                              </div>
                              <div className="text-xs sm:text-sm font-black text-white">
                                {evalItem.player.ovr} OVR
                              </div>
                            </div>
                            <span
                              className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-xs ${
                                GRADE_STYLES[evalItem.player.grade] || GRADE_STYLES.C
                              }`}
                            >
                              {evalItem.player.grade}
                            </span>
                          </div>
                        ) : pick ? (
                          <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-[#14151a] text-zinc-400 border border-[#23252c]">
                            R{pick.round}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* POST-GAME RESULTS & 17-0 SIMULATION SECTION */}
        {evaluating && (
          <div className="mt-7 bg-[#0b0b0d] border border-[#1f2025] rounded-2xl p-6 sm:p-8 text-center">
            <RefreshCw className="w-7 h-7 text-amber-400 animate-spin mx-auto mb-3" />
            <div className="text-base sm:text-lg font-bold text-white">
              Simulating 17-game season & calculating OL trench + position rankings...
            </div>
          </div>
        )}

        {evaluation && (
          <div ref={resultsRef} className="mt-7 space-y-5">
            {/* Hero Win-Loss Banner */}
            <div
              className={`rounded-2xl p-5 sm:p-7 border shadow-2xl relative overflow-hidden ${
                evaluation.is_perfect
                  ? 'bg-gradient-to-br from-amber-500/20 via-[#0e1015] to-emerald-500/15 border-amber-400/60'
                  : evaluation.wins >= 13
                  ? 'bg-gradient-to-br from-emerald-500/15 via-[#0e1015] to-[#0b0b0d] border-emerald-500/40'
                  : 'bg-gradient-to-br from-[#12141c] via-[#0d0e12] to-[#0b0b0d] border-[#1f2025]'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">
                <div>
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-amber-300 text-xs font-extrabold uppercase tracking-wider mb-2.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>{evaluation.tier_title}</span>
                  </div>
                  <div className="flex items-baseline gap-3.5 flex-wrap">
                    <div className="text-4xl sm:text-6xl font-black tracking-tight text-white">
                      {evaluation.record}
                    </div>
                    <div className="text-base sm:text-xl font-bold text-zinc-300">
                      {evaluation.playoff_finish}
                    </div>
                  </div>
                  <p className="text-zinc-300 text-xs sm:text-sm mt-2 max-w-2xl">
                    {evaluation.summary_de}
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-2.5 sm:gap-3.5 shrink-0">
                  <div className="bg-[#0b0b0d]/90 border border-[#22242c] rounded-2xl p-3 sm:p-4 text-center min-w-[82px]">
                    <div className="text-[10px] sm:text-[11px] font-bold uppercase text-zinc-400">
                      Team OVR
                    </div>
                    <div className="text-2xl sm:text-3xl font-black text-amber-400 mt-1">
                      {evaluation.team_ovr}
                    </div>
                    <div className="text-[11px] font-bold text-zinc-300 mt-0.5">
                      Grade {evaluation.team_grade}
                    </div>
                  </div>
                  <div className="bg-[#0b0b0d]/90 border border-[#22242c] rounded-2xl p-3 sm:p-4 text-center min-w-[82px]">
                    <div className="text-[10px] sm:text-[11px] font-bold uppercase text-zinc-400">
                      Offense
                    </div>
                    <div className="text-xl sm:text-2xl font-extrabold text-emerald-400 mt-1">
                      {evaluation.offense_ovr}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">OVR</div>
                  </div>
                  <div className="bg-[#0b0b0d]/90 border border-[#22242c] rounded-2xl p-3 sm:p-4 text-center min-w-[82px]">
                    <div className="text-[10px] sm:text-[11px] font-bold uppercase text-zinc-400">
                      DEF / HC
                    </div>
                    <div className="text-xl sm:text-2xl font-extrabold text-sky-400 mt-1">
                      {evaluation.defense_ovr}
                    </div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">OVR</div>
                  </div>
                </div>
              </div>

              {/* MVP & Weakest Link Callouts */}
              {evaluation.mvp && evaluation.weakest_link && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 mt-5 pt-5 border-t border-zinc-800/80">
                  <div className="flex items-center gap-3 bg-[#0b0b0d]/80 border border-emerald-500/25 rounded-xl p-3">
                    <PlayerAvatar
                      jersey={evaluation.mvp.player.jersey}
                      position={evaluation.mvp.player.position}
                      color={evaluation.mvp.player.team_color}
                      altColor={evaluation.mvp.player.team_alt_color}
                      size="lg"
                    />
                    <div className="min-w-0">
                      <div className="text-[11px] font-extrabold uppercase tracking-wider text-emerald-400">
                        ⭐ Team MVP • #{evaluation.mvp.player.pos_rank}{' '}
                        {evaluation.mvp.player.position}
                      </div>
                      <div className="text-xs sm:text-sm font-bold text-white truncate">
                        {evaluation.mvp.player.name} ({evaluation.mvp.player.ovr} OVR •{' '}
                        {evaluation.mvp.player.grade})
                      </div>
                      <div className="text-[11px] text-zinc-400 truncate">
                        {evaluation.mvp.player.stat_line}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 bg-[#0b0b0d]/80 border border-rose-500/25 rounded-xl p-3">
                    <PlayerAvatar
                      jersey={evaluation.weakest_link.player.jersey}
                      position={evaluation.weakest_link.player.position}
                      color={evaluation.weakest_link.player.team_color}
                      altColor={evaluation.weakest_link.player.team_alt_color}
                      size="lg"
                    />
                    <div className="min-w-0">
                      <div className="text-[11px] font-extrabold uppercase tracking-wider text-rose-400">
                        ⚠️ Weakest Link • #{evaluation.weakest_link.player.pos_rank}{' '}
                        {evaluation.weakest_link.player.position}
                      </div>
                      <div className="text-xs sm:text-sm font-bold text-white truncate">
                        {evaluation.weakest_link.player.name} ({evaluation.weakest_link.player.ovr}{' '}
                        OVR • {evaluation.weakest_link.player.grade})
                      </div>
                      <div className="text-[11px] text-zinc-400 truncate">
                        {evaluation.weakest_link.best_on_team_for_slot.was_optimal_on_team
                          ? 'Best available player at this position on the team'
                          : `Better on team: ${evaluation.weakest_link.best_on_team_for_slot.name} (#${evaluation.weakest_link.best_on_team_for_slot.pos_rank} ${evaluation.weakest_link.best_on_team_for_slot.position})`}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Detail Analysis Tabs */}
            <div className="bg-[#0b0b0d] border border-[#1f2025] rounded-2xl p-4 sm:p-5 shadow-xl">
              <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-[#1f2025] pb-3.5 mb-4">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar">
                  <button
                    onClick={() => setActiveResultTab('grades')}
                    className={`px-3 py-2 rounded-xl text-xs font-bold shrink-0 transition ${
                      activeResultTab === 'grades'
                        ? 'bg-white text-black'
                        : 'bg-[#131419] text-zinc-400 hover:text-white'
                    }`}
                  >
                    1. Picks & Stats
                  </button>
                  <button
                    onClick={() => setActiveResultTab('rankings')}
                    className={`px-3 py-2 rounded-xl text-xs font-bold shrink-0 transition ${
                      activeResultTab === 'rankings'
                        ? 'bg-amber-400 text-black'
                        : 'bg-[#131419] text-amber-300/90 hover:text-amber-200 border border-amber-500/30'
                    }`}
                  >
                    🏆 2. Rankings (#1–#32)
                  </button>
                  <button
                    onClick={() => setActiveResultTab('optimal')}
                    className={`px-3 py-2 rounded-xl text-xs font-bold shrink-0 transition ${
                      activeResultTab === 'optimal'
                        ? 'bg-white text-black'
                        : 'bg-[#131419] text-zinc-400 hover:text-white'
                    }`}
                  >
                    3. Optimal ({evaluation.optimal_analysis?.optimal_record})
                  </button>
                  <button
                    onClick={() => setActiveResultTab('schedule')}
                    className={`px-3 py-2 rounded-xl text-xs font-bold shrink-0 transition ${
                      activeResultTab === 'schedule'
                        ? 'bg-white text-black'
                        : 'bg-[#131419] text-zinc-400 hover:text-white'
                    }`}
                  >
                    4. 17-Game Schedule
                  </button>
                </div>

                <button
                  onClick={() => startNewGame()}
                  className="px-3.5 py-2 rounded-xl bg-white hover:bg-zinc-200 text-black text-xs font-extrabold transition flex items-center gap-1.5 shrink-0"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Play Again</span>
                </button>
              </div>

              {/* TAB 1: PICK ANALYSE */}
              {activeResultTab === 'grades' && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {evaluation.picks.map((item) => (
                    <div
                      key={item.slot_id}
                      className="p-3.5 rounded-xl bg-[#111216] border border-[#22242c] flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span
                          className={`w-11 text-center py-1 rounded-md text-xs font-extrabold border shrink-0 ${
                            POS_BADGE_COLORS[item.slot_label] || 'bg-zinc-800 text-zinc-200'
                          }`}
                        >
                          {item.slot_id}
                        </span>
                        <PlayerAvatar
                          jersey={item.player.jersey}
                          position={item.player.position}
                          color={item.player.team_color}
                          altColor={item.player.team_alt_color}
                          size="md"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs sm:text-sm font-bold text-white truncate">
                              {item.player.name}{' '}
                              <span className="text-xs text-zinc-400">({item.player.team})</span>
                            </span>
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${getRankBadgeStyle(
                                item.player.pos_rank
                              )}`}
                            >
                              #{item.player.pos_rank} {item.player.position}
                            </span>
                          </div>
                          <div className="text-[11px] text-zinc-400 line-clamp-2 mt-0.5">
                            {item.player.stat_line}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <div className="text-right">
                          <div className="text-[10px] text-zinc-500 font-bold">OVR</div>
                          <div className="text-sm font-black text-white">{item.player.ovr}</div>
                        </div>
                        <span
                          className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs ${
                            GRADE_STYLES[item.player.grade] || GRADE_STYLES.C
                          }`}
                        >
                          {item.player.grade}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 2: LEADERBOARDS */}
              {activeResultTab === 'rankings' && evaluation.leaderboards && (
                <div>
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                    <div>
                      <h4 className="text-sm font-extrabold text-white">
                        Position Rankings (#1 – #32)
                      </h4>
                      <p className="text-xs text-zinc-400">
                        Your drafted picks are highlighted in gold.
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {['QB', 'RB', 'WR', 'TE', 'OL', 'DEF', 'HC'].map((pos) => (
                        <button
                          key={pos}
                          onClick={() => setLeaderboardPos(pos)}
                          className={`px-2.5 py-1.5 rounded-lg text-xs font-extrabold transition ${
                            leaderboardPos === pos
                              ? 'bg-amber-400 text-black'
                              : 'bg-[#14151a] text-zinc-300 hover:bg-[#1c1e26] border border-[#252730]'
                          }`}
                        >
                          {pos}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-[500px] overflow-y-auto pr-1">
                    {(evaluation.leaderboards[leaderboardPos] || []).map((entry) => {
                      const isDraftedByMe = draftedPlayerIds.has(entry.id);
                      return (
                        <div
                          key={entry.id}
                          className={`p-3 rounded-xl border flex items-center justify-between gap-2.5 ${
                            isDraftedByMe
                              ? 'bg-amber-500/15 border-amber-400 shadow-md shadow-amber-500/10'
                              : 'bg-[#111216] border-[#22242c]'
                          }`}
                        >
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span
                              className={`w-9 h-8 rounded-lg flex items-center justify-center text-xs shrink-0 ${getRankBadgeStyle(
                                entry.pos_rank
                              )}`}
                            >
                              #{entry.pos_rank}
                            </span>
                            <TeamBadge
                              abbr={entry.team}
                              color={entry.team_color}
                              altColor={entry.team_alt_color}
                              size="sm"
                            />
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-xs sm:text-sm font-bold text-white truncate">
                                  {entry.name}
                                </span>
                                <span className="text-[11px] font-bold text-zinc-400">
                                  {entry.team}
                                </span>
                                {isDraftedByMe && (
                                  <span className="px-1.5 py-0.5 rounded bg-amber-400 text-black text-[9px] font-black uppercase">
                                    Your Pick
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-zinc-400 truncate">
                                {entry.stat_line}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs sm:text-sm font-black text-white">
                              {entry.ovr}
                            </span>
                            <span
                              className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center text-xs ${
                                GRADE_STYLES[entry.grade] || GRADE_STYLES.C
                              }`}
                            >
                              {entry.grade}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 3: OPTIMAL PATH */}
              {activeResultTab === 'optimal' && evaluation.optimal_analysis && (
                <div>
                  <div className="mb-4 p-3.5 rounded-xl bg-[#111216] border border-[#22242c] flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-xs sm:text-sm font-bold text-white">
                        Best Possible Roster from Your 10 Drawn Teams
                      </div>
                      <div className="text-[11px] text-zinc-400 mt-0.5">
                        Calculated via exact Bitmask Dynamic Programming
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-extrabold">
                        Optimal: {evaluation.optimal_analysis.optimal_record}
                      </span>
                      <span className="px-2.5 py-1 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-extrabold">
                        {evaluation.optimal_analysis.optimal_ovr} OVR (
                        {evaluation.optimal_analysis.optimal_grade})
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    {evaluation.optimal_analysis.picks_by_round.map((optPick) => {
                      const myPick = picksByRound[optPick.round];
                      const isSame = myPick && myPick.player_id === optPick.player.id;

                      return (
                        <div
                          key={optPick.round}
                          className={`p-3 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 ${
                            isSame
                              ? 'bg-emerald-950/20 border-emerald-500/30'
                              : 'bg-[#111216] border-[#22242c]'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="w-7 h-7 rounded-full bg-zinc-800 text-zinc-300 text-xs font-bold flex items-center justify-center shrink-0">
                              R{optPick.round}
                            </span>
                            <TeamBadge
                              abbr={optPick.team_abbr}
                              color={optPick.player.team_color}
                              altColor={optPick.player.team_alt_color}
                              size="sm"
                            />
                            <div className="min-w-0">
                              <div className="text-[11px] text-zinc-400">
                                Your Pick:{' '}
                                <strong className="text-zinc-200">
                                  {myPick
                                    ? `${myPick.player.name} (${myPick.slot_id})`
                                    : '--'}
                                </strong>
                              </div>
                              <div className="text-xs sm:text-sm font-bold text-emerald-300 truncate">
                                Optimal: {optPick.player.name} → {optPick.slot_id} (#
                                {optPick.player.pos_rank} {optPick.player.position} •{' '}
                                {optPick.player.ovr} OVR)
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 self-end sm:self-center">
                            {isSame ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-bold">
                                <CheckCircle2 className="w-3.5 h-3.5" /> Optimal Pick!
                              </span>
                            ) : (
                              <span className="text-[11px] text-zinc-400">
                                {optPick.player.stat_line}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 4: SCHEDULE */}
              {activeResultTab === 'schedule' && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                  {evaluation.schedule.map((game) => (
                    <div
                      key={game.week}
                      className={`p-3 rounded-xl border flex items-center justify-between ${
                        game.result === 'W'
                          ? 'bg-emerald-950/15 border-emerald-500/25'
                          : 'bg-rose-950/15 border-rose-500/25'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="text-[11px] font-bold text-zinc-500 w-9">
                          WK {game.week}
                        </span>
                        <TeamBadge
                          abbr={game.opponent_abbr}
                          color={game.opponent_color}
                          altColor={game.opponent_alt_color}
                          size="sm"
                        />
                        <div className="text-xs font-bold text-zinc-200 truncate">
                          {game.is_home ? 'vs' : '@'} {game.opponent_abbr}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs font-mono font-bold text-zinc-300">
                          {game.score}
                        </span>
                        <span
                          className={`w-6 h-6 rounded-md text-xs font-black flex items-center justify-center ${
                            game.result === 'W'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : 'bg-rose-500/20 text-rose-300'
                          }`}
                        >
                          {game.result}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Legal & Fair-Use Disclaimer Footer */}
      <footer className="max-w-[1020px] w-full mx-auto px-4 sm:px-6 mt-12 pt-6 border-t border-[#16171d] text-center text-[11px] text-zinc-500 space-y-1">
        <p className="font-medium text-zinc-400">
          Build A 17-0 Team • Unofficial Fan-Made Football Roster & Statistical Trivia Game
        </p>
        <p>
          All factual player statistics and historical season metrics are public domain. This website is not affiliated with, endorsed by, or sponsored by the National Football League (NFL), NFLPA, or any professional football franchise.
        </p>
      </footer>

      {/* Info Modal */}
      {showInfoModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1015] border border-[#22242c] rounded-2xl max-w-lg w-full p-5 sm:p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base sm:text-lg font-extrabold text-white">
                How to Play & Rating Formula
              </h3>
              <button
                onClick={() => setShowInfoModal(false)}
                className="p-1 rounded-lg text-zinc-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3 text-xs sm:text-sm text-zinc-300 leading-relaxed">
              <p>
                <strong>1. Ultimate 10-Slot Roster:</strong> Each round spins a random team. Pick one player or unit to fill your 10-slot lineup (<code>QB, 2× RB, 2× WR, 2× TE, OL, DEF, HC</code>).
              </p>
              <p>
                <strong>2. Trench-Based OL Rating:</strong> Offensive Lines are ranked strictly by <strong>Pass Protection (Pass Block Win Rate & low Sack Rate Allowed)</strong> and <strong>Run Blocking (RB Yards Per Carry & RB Rushing YPG)</strong> — completely independent of QB fantasy points or team scoring.
              </p>
              <p>
                <strong>3. 17-Game Simulation & Optimal Path:</strong> After Round 10, your roster is simulated across a 17-game schedule and compared against the mathematically optimal lineup via Bitmask Dynamic Programming.
              </p>
            </div>
            <div className="mt-5 pt-4 border-t border-[#22242c] flex items-center justify-between gap-3">
              <div className="inline-flex items-center gap-1.5 text-[11px] text-emerald-400 font-semibold">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Auto-Synced Daily (24h Cron) • Anti-Cheat Verified</span>
              </div>
              <button
                onClick={() => setShowInfoModal(false)}
                className="px-4 py-2 rounded-xl bg-white text-black text-xs font-extrabold"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
