import axios from 'axios';
import { MonitoringData, Config, InstrumentData, InstrumentFullData } from '../types';

// В режиме разработки используем прокси, в продакшене - переменную окружения
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  : '';

export const api = {
  // Получить текущие данные мониторинга
  async getMonitoringData(): Promise<MonitoringData> {
    const response = await axios.get(`${API_BASE_URL}/api/data`);
    return response.data;
  },

  // Получить данные по инструментам (для таблицы)
  async getInstruments(): Promise<InstrumentData[]> {
    const response = await axios.get(`${API_BASE_URL}/api/all-instruments`);
    return response.data;
  },

  // Получить полные данные по конкретному инструменту (все фьючерсы)
  async getInstrumentFullData(instrument: string): Promise<InstrumentFullData> {
    const response = await axios.get(`${API_BASE_URL}/api/instruments/${instrument}`);
    return response.data;
  },

  // Получить конфигурацию
  async getConfig(): Promise<Config> {
    const response = await axios.get(`${API_BASE_URL}/api/config`);
    return response.data;
  },

  // Обновить конфигурацию
  async updateConfig(config: Partial<Config>): Promise<{ success: boolean; message: string }> {
    const response = await axios.put(`${API_BASE_URL}/api/config`, config);
    return response.data;
  },
};

// WebSocket подключение
export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private listeners: Set<(data: InstrumentData[]) => void> = new Set();

  connect(endpoint: string = '/ws/instruments') {
    // В режиме разработки используем localhost:8000, в продакшене - текущий хост
    const wsBaseUrl = process.env.NODE_ENV === 'production'
      ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
      : 'ws://localhost:8000';
    const wsUrl = wsBaseUrl + endpoint;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.listeners.forEach(listener => listener(data));
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...');
      this.reconnectTimeout = setTimeout(() => {
        this.connect(endpoint);
      }, 3000);
    };
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  subscribe(listener: (data: InstrumentData[]) => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }
}

export const wsService = new WebSocketService();

