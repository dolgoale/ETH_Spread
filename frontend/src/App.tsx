import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import MainLayout from './components/Layout/MainLayout';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import AssetPage from './pages/AssetPage';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <MainLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/asset/ETH" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/asset/:symbol" element={<AssetPage />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </MainLayout>
      </Router>
    </ThemeProvider>
  );
}

export default App;
