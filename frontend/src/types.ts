export type GameMode = 'ultimate';

export interface RosterSlot {
  slot_id: string;
  label: string;
  allowed: string[];
  weight: number;
  color: string;
}

export interface DraftPlayer {
  id: string;
  espn_id: string;
  name: string;
  team: string;
  team_name: string;
  team_color?: string;
  team_alt_color?: string;
  position: string;
  jersey: string;
  headshot: string;
  age: number | null;
  experience: number | null;
  college: string;
  depth_order: number;
  depth_label: string;
  is_starter: boolean;
  // Revealed only after game completion
  ovr?: number;
  grade?: string;
  pos_rank?: number;
  pos_total?: number;
  pts_ppr?: number;
  ppg_ppr?: number;
  stat_line?: string;
}

export interface RoundTeam {
  round: number;
  abbr: string;
  name: string;
  short_name: string;
  location: string;
  nickname: string;
  color: string;
  alt_color: string;
  logo: string;
  record_2026?: string;
  players: DraftPlayer[];
}

export interface GameSession {
  mode: GameMode;
  season: string;
  session_token: string;
  total_rounds: number;
  slots: RosterSlot[];
  rounds: RoundTeam[];
}

export interface UserPick {
  round: number;
  slot_id: string;
  player_id: string;
  team_abbr: string;
  team_color: string;
  team_alt_color: string;
  player: DraftPlayer;
}

export interface EvaluatedPick {
  round: number;
  slot_id: string;
  slot_label: string;
  weight: number;
  rank_badge: string;
  player: Required<DraftPlayer>;
  best_on_team_for_slot: {
    name: string;
    ovr: number;
    pos_rank: number;
    position: string;
    grade: string;
    was_optimal_on_team: boolean;
  };
  nfl_number_one?: {
    name: string;
    team: string;
    ovr: number;
  } | null;
}

export interface LeaderboardEntry {
  id: string;
  name: string;
  team: string;
  team_color?: string;
  team_alt_color?: string;
  position: string;
  pos_rank: number;
  pos_total: number;
  ovr: number;
  grade: string;
  pts_ppr: number;
  stat_line: string;
  headshot: string;
}

export interface ScheduleGame {
  week: number;
  opponent_abbr: string;
  opponent_name: string;
  opponent_color?: string;
  opponent_alt_color?: string;
  opponent_logo: string;
  is_home: boolean;
  difficulty: number;
  result: 'W' | 'L';
  score: string;
  my_score: number;
  opp_score: number;
}

export interface OptimalRoundPick {
  round: number;
  team_abbr: string;
  slot_id: string;
  slot_label: string;
  player: Required<DraftPlayer>;
}

export interface OptimalAnalysis {
  optimal_ovr: number;
  optimal_grade: string;
  optimal_record: string;
  optimal_wins: number;
  optimal_losses: number;
  picks_by_round: OptimalRoundPick[];
}

export interface EvaluationResult {
  mode: GameMode;
  season: string;
  team_ovr: number;
  team_grade: string;
  offense_ovr: number;
  defense_ovr: number;
  wins: number;
  losses: number;
  record: string;
  is_perfect: boolean;
  tier_title: string;
  playoff_finish: string;
  summary_de: string;
  bottleneck_note: string | null;
  mvp: EvaluatedPick | null;
  weakest_link: EvaluatedPick | null;
  picks: EvaluatedPick[];
  schedule: ScheduleGame[];
  optimal_analysis: OptimalAnalysis;
  leaderboards: Record<string, LeaderboardEntry[]>;
}

export interface RunHistoryEntry {
  id: string;
  timestamp: string;
  mode: GameMode;
  record: string;
  wins: number;
  losses: number;
  team_ovr: number;
  team_grade: string;
}
