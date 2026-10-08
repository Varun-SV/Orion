export const collections = {
  movies: 'Movies',
  series: 'TV series',
  anime: 'Anime',
  anime_films: 'Anime films',
  web_series: 'Web series',
  music: 'Music',
  books: 'Books',
} as const;
export type Kind = keyof typeof collections;
export type Theme = 'ivory' | 'clay' | 'night';
export type Metadata = Record<string, unknown>;
export interface Decision {
  item_id: string;
  provider: string;
  provider_id: string;
  metadata: Metadata;
  evidence: string[];
}
export interface MediaItem {
  id: string;
  source_id: string;
  path: string;
  kind: Kind;
  status: 'pending' | 'approved' | 'organised' | 'error' | 'unavailable' | 'no_match';
  signature: Metadata;
  metadata: Metadata;
  decision: Decision | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Candidate {
  provider: string;
  provider_id: string;
  title: string;
  year: string;
  metadata: Metadata;
  evidence: string[];
}
export interface Overview {
  counts: Record<Kind, number>;
  status_counts: Record<string, number>;
  total: number;
  review: number;
  indexed_bytes: number;
  sources: number;
  destinations: number;
  jobs_running: number;
}
export interface Settings {
  theme: Theme;
  view: 'grid' | 'list';
  fingerprint_enabled: boolean;
  audd_enabled: boolean;
  default_destination: string | null;
  providers: Partial<Record<Kind, string | null>>;
}
export interface Source {
  id: string;
  path: string;
  label: string;
  kind: Kind | 'auto';
  watch: number;
  archived: boolean;
}
export interface Destination {
  id: string;
  path: string;
  label: string;
}
export interface Provider {
  id: string;
  label: string;
  requires_key: boolean;
  configured: boolean;
  storage: string;
  health: string;
  detail: string;
  consent_enabled: boolean;
}
export interface Operation {
  id: string;
  plan_id: string;
  item_id: string;
  kind: string;
  source: string;
  destination: string;
  expected_signature: Metadata;
  state: string;
  verification: Metadata;
}
export interface Issue {
  code: string;
  detail: string;
  operation_id: string;
  item_id: string;
}
export interface Plan {
  id: string;
  revision: number;
  operations: Operation[];
  issues: Issue[];
}
export interface Job {
  id: string;
  kind: string;
  state: string;
  progress: {
    phase?: string;
    items_done?: number;
    items_total?: number;
    bytes_done?: number;
    bytes_total?: number;
  };
  result: Metadata | null;
  error: string | null;
}
export interface Batch {
  id: string;
  plan_id: string;
  state: string;
  data: Metadata;
  created_at: string;
}
export interface ActivityRecord {
  id: number;
  action: string;
  detail: string;
  status: string;
  created_at: string;
}
export const text = (value: unknown, fallback = ''): string =>
  typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;
export const title = (item: MediaItem) =>
  text(
    item.decision?.metadata.title ?? item.metadata.title,
    item.path.split(/[\\/]/).pop() ?? 'Untitled',
  );
export const bytes = (value: number) =>
  value >= 1073741824
    ? `${(value / 1073741824).toFixed(1)} GB`
    : value >= 1048576
      ? `${(value / 1048576).toFixed(1)} MB`
      : value >= 1024
        ? `${(value / 1024).toFixed(1)} KB`
        : `${value} B`;
export const active = (job: Job) => ['queued', 'running', 'cancelling'].includes(job.state);
export interface NamingProfile {
  id: string;
  label: string;
  version: number;
  kind: Kind | 'auto';
  movie_template: string;
  folder_template: string;
  episode_template: string;
  music_template: string;
  book_template: string;
  quality_keys: string[];
}
export interface Comparison {
  exact: boolean;
  items: {
    item_id: string;
    path: string;
    kind: string;
    title: string;
    bytes: number;
    provider: string;
    provider_id: string;
    quality: Metadata;
    edition: string;
    sha256: string | null;
  }[];
  exact_groups: string[][];
  version_groups: { item_ids: string[]; evidence: string[] }[];
  errors: { item_id: string; code: string }[];
}
export interface ServerStatus {
  enabled: boolean;
  url: string;
  server_type: 'jellyfin' | 'emby';
  user_id: string;
  auto_refresh: boolean;
  configured: boolean;
  storage: string;
  health: string;
  detail: string;
}
export interface ServerItem {
  edition: string;
  is_virtual: boolean;
  id: string;
  name: string;
  type: string;
  year: number | null;
  path: string;
  resolution: string;
  provider_ids: Record<string, string>;
  media_sources: Metadata[];
  evidence?: string[];
}
export interface GapReport {
  episodes: { season: number; episode: number; title: string; air_date: string; state: string }[];
  state: string;
  missing: [number, number][];
  unaired: [number, number][];
  unknown_air_date: [number, number][];
  present: [number, number][];
  error: string | null;
  catalogue_cached: boolean;
  catalogue_updated_at: string;
}
