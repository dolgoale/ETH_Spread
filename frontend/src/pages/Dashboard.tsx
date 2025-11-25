import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';
import { api, wsService } from '../services/api';
import { InstrumentData } from '../types';

const Dashboard: React.FC = () => {
  const [instruments, setInstruments] = useState<InstrumentData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  useEffect(() => {
    // Загрузка начальных данных
    const loadData = async () => {
      try {
        const data = await api.getInstruments();
        if (Array.isArray(data)) {
          setInstruments(data);
          setLastUpdate(new Date());
        } else {
          console.error('Получены некорректные данные:', data);
          setError('Получены некорректные данные с сервера');
        }
        setLoading(false);
      } catch (err) {
        console.error('Ошибка загрузки данных:', err);
        setError('Ошибка загрузки данных');
        setLoading(false);
      }
    };

    loadData();

    // Подключение к WebSocket
    wsService.connect('/ws/instruments');
    const unsubscribe = wsService.subscribe((data: InstrumentData[] | any) => {
      if (Array.isArray(data)) {
        setInstruments(data);
        setLastUpdate(new Date());
        setError(null);
      } else {
        console.error('WebSocket получил некорректные данные:', data);
      }
    });

    return () => {
      unsubscribe();
      wsService.disconnect();
    };
  }, []);

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toFixed(decimals);
  };

  const formatPercent = (num: number): string => {
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  };

  const getSpreadColor = (spread: number): 'success' | 'warning' | 'error' => {
    if (spread < -0.5) return 'error';
    if (spread < 0) return 'warning';
    return 'success';
  };

  const getROCColor = (roc: number, threshold: number): 'success' | 'warning' | 'default' => {
    if (roc > threshold) return 'success';
    if (roc > threshold * 0.7) return 'warning';
    return 'default';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Мониторинг спредов
        </Typography>
        {lastUpdate && (
          <Typography variant="body2" color="text.secondary">
            Обновлено: {lastUpdate.toLocaleTimeString('ru-RU')}
          </Typography>
        )}
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Актив</TableCell>
              <TableCell align="right">Бессрочный</TableCell>
              <TableCell align="right">Срочный</TableCell>
              <TableCell align="right">Спред %</TableCell>
              <TableCell align="right">Funding Rate</TableCell>
              <TableCell align="right">Avg FR</TableCell>
              <TableCell align="right">Дней до эксп.</TableCell>
              <TableCell align="right">Прибыль %</TableCell>
              <TableCell align="right">ROC годовых</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {instruments.map((instrument) => (
              <TableRow
                key={instrument.futures_symbol}
                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                hover
              >
                <TableCell component="th" scope="row">
                  <Box display="flex" alignItems="center" gap={1}>
                    <Typography variant="body1" fontWeight="bold">
                      {instrument.symbol}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {instrument.futures_symbol}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    ${formatNumber(instrument.perpetual_price)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    ${formatNumber(instrument.futures_price)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={formatPercent(instrument.spread_percent)}
                    color={getSpreadColor(instrument.spread_percent)}
                    size="small"
                    icon={instrument.spread_percent >= 0 ? <TrendingUp /> : <TrendingDown />}
                  />
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    {formatPercent(instrument.funding_rate * 100)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" color="text.secondary">
                    {formatPercent(instrument.avg_funding_rate * 100)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">
                    {formatNumber(instrument.days_until_expiration, 1)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    color={instrument.net_profit_percent > 0 ? 'success.main' : 'error.main'}
                  >
                    {formatPercent(instrument.net_profit_percent)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={formatPercent(instrument.return_on_capital)}
                    color={getROCColor(instrument.return_on_capital, 50)}
                    size="small"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {instruments.length === 0 && (
        <Box mt={3}>
          <Alert severity="info">Нет данных для отображения</Alert>
        </Box>
      )}
    </Box>
  );
};

export default Dashboard;

