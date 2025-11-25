export interface SpreadData {
  perpetual_symbol: string;
  futures_symbol: string;
  perpetual_price: number;
  futures_price: number;
  spread: number;
  spread_percent: number;
  timestamp: string;
}

export interface FundingRateData {
  symbol: string;
  current_rate: number;
  average_rate: number;
  timestamp: string;
}

export interface FutureData {
  symbol: string;
  mark_price: number;
  last_price: number;
  timestamp: number;
  delivery_time?: number;
  days_until_expiration?: number;
  spread_percent?: number;
  fair_futures_price?: number;
  fair_spread_percent?: number;
  funding_rate_until_expiration?: number;
  funding_rate_365days_until_expiration?: number;
  net_profit_current_fr?: number;
  net_profit_365days_fr?: number;
  net_profit_usdt?: number;
  return_on_capital?: number;
  net_profit_usdt_365days?: number;
  return_on_capital_365days?: number;
  average_fr_days_used?: number;
}

export interface InstrumentFullData {
  perpetual: {
    symbol: string;
    mark_price: number;
    last_price: number;
    timestamp: number;
    spot_price: number;
    current_funding_rate: number;
    total_funding_rate_3months: number;
    total_funding_rate_6months: number;
    total_funding_rate_365days: number;
  };
  futures: FutureData[];
  risk_free_rate_annual: number;
}

export interface InstrumentData {
  symbol: string;
  perpetual_symbol: string;
  futures_symbol: string;
  perpetual_price: number;
  futures_price: number;
  spread_percent: number;
  funding_rate: number;
  avg_funding_rate: number;
  days_until_expiration: number;
  net_profit_percent: number;
  return_on_capital: number;
  timestamp: string;
}

export interface MonitoringData {
  spreads: { [key: string]: SpreadData };
  funding_rate: FundingRateData | null;
  timestamp: string;
}

export interface Config {
  spread_threshold_percent: number;
  funding_rate_history_days: number;
  monitoring_interval_seconds: number;
  return_on_capital_threshold: number;
  capital_usdt: number;
  leverage: number;
  risk_free_rate: number;
  perpetual_symbol: string;
}
