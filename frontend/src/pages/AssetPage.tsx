import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
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
  CircularProgress,
  Alert,
  Card,
  CardContent,
} from '@mui/material';
import { api } from '../services/api';
import { InstrumentFullData, FutureData, Config } from '../types';

const AssetPage: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const [data, setData] = useState<InstrumentFullData | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [updateCount, setUpdateCount] = useState(0);
  const [isUpdating, setIsUpdating] = useState(false);

  const cryptoNames: { [key: string]: string } = {
    ETH: 'Ethereum',
    BTC: 'Bitcoin',
    SOL: 'Solana',
  };

  const loadConfig = useCallback(async () => {
    try {
      const configData = await api.getConfig();
      setConfig(configData);
    } catch (err) {
      console.error('Ошибка загрузки конфигурации:', err);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    
    const loadData = async () => {
      try {
        setIsUpdating(true);
        const currentSymbol = symbol || 'ETH';
        console.log('Загрузка данных для:', currentSymbol);
        const instrumentData = await api.getInstrumentFullData(currentSymbol);
        
        if (isMounted) {
          setData(instrumentData);
          setLastUpdate(new Date());
          setUpdateCount(prev => prev + 1);
          setLoading(false);
          setError(null);
        }
      } catch (err) {
        console.error('Ошибка загрузки данных:', err);
        if (isMounted) {
          setError('Ошибка загрузки данных');
          setLoading(false);
        }
      } finally {
        if (isMounted) {
          setIsUpdating(false);
        }
      }
    };

    // Сброс состояния при смене актива
    setLoading(true);
    setError(null);
    
    // Первая загрузка
    loadData();
    loadConfig();
    
    // Обновляем данные каждую секунду (используем кэш backend)
    const interval = setInterval(() => {
      loadData();
    }, 1000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [symbol, loadConfig]);

  const formatNumber = (num: number | undefined, decimals: number = 2): string => {
    if (num === undefined || num === null) return 'N/A';
    return num.toFixed(decimals);
  };

  const formatPercent = (num: number | undefined, decimals: number = 4): string => {
    if (num === undefined || num === null) return 'N/A';
    // Умножаем на 100, так как backend возвращает в десятичном формате (0.0001 = 0.01%)
    const percentValue = num * 100;
    return `${percentValue >= 0 ? '' : ''}${percentValue.toFixed(decimals)}%`;
  };

  const formatPercentAlready = (num: number | undefined, decimals: number = 2): string => {
    if (num === undefined || num === null) return 'N/A';
    // Число уже в процентах (например, 3.89 = 3.89%), не нужно умножать на 100
    return `${num >= 0 ? '' : ''}${num.toFixed(decimals)}%`;
  };

  const getColor = (value: number | undefined): string => {
    if (value === undefined || value === null) return '#6b7280';
    return value > 0 ? '#10b981' : value < 0 ? '#ef4444' : '#6b7280';
  };

  const shouldHighlight = (future: FutureData): boolean => {
    return !!(
      future.spread_percent !== undefined &&
      future.funding_rate_until_expiration !== undefined &&
      future.fair_spread_percent !== undefined &&
      future.net_profit_current_fr !== undefined &&
      future.spread_percent < future.funding_rate_until_expiration &&
      future.spread_percent < future.fair_spread_percent &&
      future.net_profit_current_fr > 0
    );
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box>
        <Alert severity="error">{error || 'Данные не найдены'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      {/* Заголовок */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box display="flex" alignItems="center" gap={2}>
          <Typography variant="h4" component="h1" gutterBottom>
            {symbol} - {cryptoNames[symbol || '']}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {data.perpetual.symbol}
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          {isUpdating && (
            <Box display="flex" alignItems="center" gap={1}>
              <CircularProgress size={16} />
              <Typography variant="caption" color="primary">
                Обновление...
              </Typography>
            </Box>
          )}
          {lastUpdate && (
            <Box display="flex" flexDirection="column" alignItems="flex-end">
              <Typography variant="body2" color="text.secondary">
                Обновлено: {lastUpdate.toLocaleTimeString('ru-RU')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Обновлений: {updateCount}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>

      {/* Карточки с основными метриками */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: '1fr 1fr 1fr', lg: 'repeat(6, 1fr)' },
          gap: 2,
          mb: 3,
        }}
      >
        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Бессрочный (Mark Price)
            </Typography>
            <Typography variant="h6">
              ${formatNumber(data.perpetual.mark_price)}
            </Typography>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Spot Price
            </Typography>
            <Typography variant="h6">
              ${formatNumber(data.perpetual.spot_price)}
            </Typography>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Текущий FR (8 часов)
            </Typography>
            <Typography variant="h6">
              {formatPercent(data.perpetual.current_funding_rate)}
            </Typography>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Суммарный FR (3 месяца)
            </Typography>
            <Typography variant="h6">
              {formatPercent(data.perpetual.total_funding_rate_3months)}
            </Typography>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Суммарный FR (6 месяцев)
            </Typography>
            <Typography variant="h6">
              {formatPercent(data.perpetual.total_funding_rate_6months)}
            </Typography>
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <Typography color="text.secondary" gutterBottom variant="body2">
              Суммарный FR (365 дней)
            </Typography>
            <Typography variant="h6">
              {formatPercent(data.perpetual.total_funding_rate_365days)}
            </Typography>
          </CardContent>
        </Card>
      </Box>

      {/* Количество контрактов */}
      {config && (
        <Paper sx={{ p: 2, mb: 3, backgroundColor: 'rgba(144, 202, 249, 0.08)' }}>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="body1" color="text.secondary">
              Количество контрактов на каждой "ноге":
            </Typography>
            <Typography variant="h5" fontWeight="bold" color="primary">
              {Math.floor((config.capital_usdt / 2) / (data.perpetual.mark_price * (1 / config.leverage)))}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Капитал: ${formatNumber(config.capital_usdt, 0)} USDT | Плечо: {config.leverage}x
          </Typography>
        </Paper>
      )}


      {/* Таблица фьючерсов */}
      <TableContainer component={Paper}>
        <Table size="small" sx={{ minWidth: 1200 }}>
          <TableHead>
            <TableRow>
              <TableCell>Символ</TableCell>
              <TableCell align="right">Дней до экспирации</TableCell>
              <TableCell align="right">Mark Price</TableCell>
              <TableCell align="right" title="Разница между ценой срочного и бессрочного фьючерса в %">
                Спред %
              </TableCell>
              <TableCell align="right" title="Спред между бессрочным фьючерсом и расчетной справедливой ценой срочного фьючерса">
                Справедливый спред %
              </TableCell>
              <TableCell align="right" title="Суммарный Funding Rate за количество дней до экспирации (на базе 30 дней)">
                FR за кол-во дней
              </TableCell>
              <TableCell align="right" title="FR за количество дней до экспирации на базе среднего FR за последний год">
                FR (за 1 год)
              </TableCell>
              <TableCell align="right" title="Чистая прибыль на базе исторического FR за 30 дней (% и USDT)">
                Чистая прибыль (FR)
              </TableCell>
              <TableCell align="right" title="Чистая прибыль на базе среднего FR за последний год (% и USDT)">
                Чистая прибыль (FR за 1 год)
              </TableCell>
              <TableCell align="right" title="Доходность на капитал в % годовых (на базе FR до экспирации)">
                ROC % годовых (FR до экспирации)
              </TableCell>
              <TableCell align="right" title="Доходность на капитал в % годовых (на базе FR за 1 год)">
                ROC % годовых (FR за 1 год)
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.futures.map((future) => {
              const isHighlighted = shouldHighlight(future);
              return (
                <TableRow
                  key={future.symbol}
                  sx={{
                    fontWeight: isHighlighted ? 'bold' : 'normal',
                    backgroundColor: isHighlighted ? 'rgba(16, 185, 129, 0.1)' : 'inherit',
                    '&:hover': {
                      backgroundColor: isHighlighted ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                    },
                  }}
                >
                  <TableCell>{future.symbol}</TableCell>
                  <TableCell align="right">
                    {future.days_until_expiration ? `${formatNumber(future.days_until_expiration, 1)} дней` : 'N/A'}
                  </TableCell>
                  <TableCell align="right">${formatNumber(future.mark_price)}</TableCell>
                  <TableCell align="right" sx={{ color: getColor(future.spread_percent) }}>
                    {formatPercentAlready(future.spread_percent)}
                  </TableCell>
                  <TableCell align="right" sx={{ color: getColor(future.fair_spread_percent) }}>
                    {formatPercentAlready(future.fair_spread_percent)}
                  </TableCell>
                  <TableCell align="right">{formatPercentAlready(future.funding_rate_until_expiration)}</TableCell>
                  <TableCell align="right">{formatPercentAlready(future.funding_rate_365days_until_expiration)}</TableCell>
                  <TableCell align="right" sx={{ color: getColor(future.net_profit_current_fr) }}>
                    {formatPercentAlready(future.net_profit_current_fr)}
                    {future.net_profit_usdt !== undefined && (
                      <span style={{ fontSize: '0.85em', opacity: 0.8 }}>
                        {' '}(${formatNumber(future.net_profit_usdt, 2)})
                      </span>
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ color: getColor(future.net_profit_365days_fr) }}>
                    {formatPercentAlready(future.net_profit_365days_fr)}
                    {future.net_profit_usdt_365days !== undefined && (
                      <span style={{ fontSize: '0.85em', opacity: 0.8 }}>
                        {' '}(${formatNumber(future.net_profit_usdt_365days, 2)})
                      </span>
                    )}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold', color: getColor(future.return_on_capital) }}>
                    {future.return_on_capital !== undefined ? `${formatNumber(future.return_on_capital, 2)}%` : 'N/A'}
                  </TableCell>
                  <TableCell align="right" sx={{ fontWeight: 'bold', color: getColor(future.return_on_capital_365days) }}>
                    {future.return_on_capital_365days !== undefined ? `${formatNumber(future.return_on_capital_365days, 2)}%` : 'N/A'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Справочная информация о комиссиях */}
      <Paper sx={{ p: 2, mt: 3, backgroundColor: 'rgba(0, 0, 0, 0.02)' }}>
        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold', mb: 1 }}>
          💰 Комиссии ByBit VIP2 (учтены в расчете чистой прибыли)
        </Typography>
        <Box component="ul" sx={{ m: 0, pl: 2 }}>
          <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
            Покупка срочного фьючерса (long): <strong>0.0290%</strong>
          </Typography>
          <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
            Продажа бессрочного фьючерса (short): <strong>0.0290%</strong>
          </Typography>
          <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
            Продажа срочного фьючерса (закрытие long): <strong>0.0290%</strong>
          </Typography>
          <Typography component="li" variant="body2" sx={{ mb: 1 }}>
            Покупка бессрочного фьючерса (закрытие short): <strong>0.0290%</strong>
          </Typography>
        </Box>
        <Typography variant="body2" sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(0, 0, 0, 0.1)' }}>
          <strong>Итого комиссий за полный цикл сделки:</strong> 4 сделки × 0.0290% = <strong>0.1160%</strong>
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Примечание: Комиссии вычитаются из чистой прибыли. В скобках указана прибыль в USDT.
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          <strong>"Чистая прибыль (FR)":</strong> Суммарный FR за количество дней до экспирации фьючерса (на основе среднего FR за последние 30 дней) минус спред и комиссии.
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          <strong>"Чистая прибыль (FR за 1 год)":</strong> Суммарный FR за количество дней до экспирации фьючерса (на основе среднего FR за последние 365 дней) минус спред и комиссии.
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          <strong>"ROC % годовых":</strong> Доходность на капитал в процентах годовых. Цвет зависит от знака: зеленый - положительная, красный - отрицательная.
        </Typography>
      </Paper>

      {data.futures.length === 0 && (
        <Box mt={3}>
          <Alert severity="info">Нет данных по срочным фьючерсам</Alert>
        </Box>
      )}
    </Box>
  );
};

export default AssetPage;
