import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Stack,
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { api } from '../services/api';
import { Config } from '../types';

const Settings: React.FC = () => {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const data = await api.getConfig();
      setConfig(data);
      setLoading(false);
    } catch (err) {
      setMessage({ type: 'error', text: 'Ошибка загрузки настроек' });
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!config) return;

    setSaving(true);
    setMessage(null);

    try {
      const result = await api.updateConfig(config);
      setMessage({ type: 'success', text: result.message || 'Настройки успешно сохранены' });
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.message || 'Ошибка сохранения настроек',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field: keyof Config, value: string) => {
    if (!config) return;

    const numValue = parseFloat(value);
    setConfig({
      ...config,
      [field]: isNaN(numValue) ? value : numValue,
    });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (!config) {
    return (
      <Box>
        <Alert severity="error">Не удалось загрузить настройки</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" mb={3}>
        Настройки
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 3 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Stack spacing={3}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
            <TextField
              fullWidth
              label="Плечо"
              type="number"
              value={config.leverage}
              onChange={(e) => handleChange('leverage', e.target.value)}
              helperText="Кредитное плечо (1-100)"
            />

            <TextField
              fullWidth
              label="Капитал (USDT)"
              type="number"
              value={config.capital_usdt}
              onChange={(e) => handleChange('capital_usdt', e.target.value)}
              helperText="Размер капитала для расчетов"
            />

            <TextField
              fullWidth
              label="Безрисковая ставка (годовая)"
              type="number"
              inputProps={{ step: 0.01, min: 0, max: 1 }}
              value={config.risk_free_rate}
              onChange={(e) => handleChange('risk_free_rate', e.target.value)}
              helperText="Безрисковая ставка для расчета справедливого спреда (0.05 = 5%)"
            />

            <TextField
              fullWidth
              label="Порог доходности (%)"
              type="number"
              value={config.return_on_capital_threshold}
              onChange={(e) => handleChange('return_on_capital_threshold', e.target.value)}
              helperText="Минимальная годовая доходность для уведомления"
            />
          </Box>

          <Box display="flex" justifyContent="flex-end" gap={2}>
            <Button
              variant="outlined"
              onClick={loadConfig}
              disabled={saving}
            >
              Отменить
            </Button>
            <Button
              variant="contained"
              startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
              onClick={handleSave}
              disabled={saving}
            >
              Сохранить
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Box>
  );
};

export default Settings;

