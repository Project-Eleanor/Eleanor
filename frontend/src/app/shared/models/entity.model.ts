export type EntityType = 'host' | 'user' | 'ip' | 'domain' | 'file' | 'process' | 'url' | 'email';

export interface Entity {
  id: string;
  entity_type: EntityType;
  value: string;
  first_seen: string | null;
  last_seen: string | null;
  attributes: Record<string, unknown>;
  enrichment: EntityEnrichment | null;
  related_cases: string[];
  risk_score: number | null;
  tags: string[];
}

export interface EntityEnrichment {
  source: string;
  enriched_at: string;
  data: Record<string, unknown>;
  iocs: IOC[];
  reputation: ReputationScore | null;
}

export interface IOC {
  type: string;
  value: string;
  confidence: number;
  source: string;
  first_seen: string | null;
  last_seen: string | null;
  tags: string[];
}

export interface ReputationScore {
  score: number;
  category: string;
  sources: string[];
  details: Record<string, unknown>;
}

export interface HostProfile {
  hostname: string;
  ip_addresses: string[];
  mac_addresses: string[];
  os_name: string | null;
  os_version: string | null;
  domain: string | null;
  last_seen: string | null;
  agent_id: string | null;
  agent_version: string | null;
  recent_events: EntityEvent[];
  installed_software: Software[];
  open_ports: Port[];
}

export interface UserProfile {
  username: string;
  display_name: string | null;
  email: string | null;
  domain: string | null;
  sid: string | null;
  groups: string[];
  last_logon: string | null;
  logon_history: LogonEvent[];
  permissions: string[];
}

export interface IPProfile {
  ip_address: string;
  ip_version: 4 | 6;
  is_private: boolean;
  geolocation: GeoLocation | null;
  asn: ASNInfo | null;
  reputation: ReputationScore | null;
  related_domains: string[];
  related_connections: Connection[];
}

export interface EntityEvent {
  timestamp: string;
  event_type: string;
  description: string;
  source: string;
}

export interface Software {
  name: string;
  version: string;
  vendor: string | null;
  install_date: string | null;
}

export interface Port {
  port: number;
  protocol: string;
  service: string | null;
  state: string;
}

export interface LogonEvent {
  timestamp: string;
  logon_type: string;
  source_ip: string | null;
  source_host: string | null;
  success: boolean;
}

export interface GeoLocation {
  country: string;
  country_code: string;
  city: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface ASNInfo {
  asn: number;
  name: string;
  description: string | null;
}

export interface Connection {
  timestamp: string;
  direction: 'inbound' | 'outbound';
  remote_ip: string;
  remote_port: number;
  local_port: number;
  protocol: string;
}
