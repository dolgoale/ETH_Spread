import React, { useState } from 'react';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Settings as SettingsIcon,
  ShowChart as ShowChartIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const drawerWidth = 240;

interface MainLayoutProps {
  children: React.ReactNode;
}

// Иконки для криптовалют
const cryptoIcons: { [key: string]: string } = {
  ETH: '⟠',
  BTC: '₿',
  SOL: '◎',
};

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const cryptoAssets = [
    { symbol: 'ETH', name: 'Ethereum', path: '/asset/ETH', color: '#627EEA' },
    { symbol: 'BTC', name: 'Bitcoin', path: '/asset/BTC', color: '#F7931A' },
    { symbol: 'SOL', name: 'Solana', path: '/asset/SOL', color: '#14F195' },
  ];

  const drawer = (
    <div>
      <Toolbar>
        <ShowChartIcon sx={{ mr: 1 }} />
        <Typography variant="h6" noWrap component="div">
          Spread Monitor
        </Typography>
      </Toolbar>
      <Divider />
      
      {/* Активы */}
      <Box sx={{ px: 2, py: 1 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
          АКТИВЫ
        </Typography>
      </Box>
      <List>
        {cryptoAssets.map((asset) => (
          <ListItem key={asset.symbol} disablePadding>
            <ListItemButton
              selected={location.pathname === asset.path}
              onClick={() => {
                navigate(asset.path);
                setMobileOpen(false);
              }}
              sx={{
                '&.Mui-selected': {
                  backgroundColor: 'rgba(144, 202, 249, 0.16)',
                  '&:hover': {
                    backgroundColor: 'rgba(144, 202, 249, 0.24)',
                  },
                },
              }}
            >
              <ListItemIcon>
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    bgcolor: location.pathname === asset.path ? asset.color : 'rgba(255, 255, 255, 0.1)',
                    fontSize: '1.2rem',
                    fontWeight: 'bold',
                  }}
                >
                  {cryptoIcons[asset.symbol]}
                </Avatar>
              </ListItemIcon>
              <ListItemText 
                primary={asset.symbol}
                secondary={asset.name}
                primaryTypographyProps={{ fontWeight: 'bold' }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      
      <Divider sx={{ my: 1 }} />
      
      {/* Настройки */}
      <List>
        <ListItem disablePadding>
          <ListItemButton
            selected={location.pathname === '/settings'}
            onClick={() => {
              navigate('/settings');
              setMobileOpen(false);
            }}
          >
            <ListItemIcon sx={{ color: location.pathname === '/settings' ? 'primary.main' : 'inherit' }}>
              <SettingsIcon />
            </ListItemIcon>
            <ListItemText primary="Настройки" />
          </ListItemButton>
        </ListItem>
      </List>
    </div>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { sm: 'none' } }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div">
            Мониторинг спредов криптовалют
          </Typography>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true, // Better open performance on mobile.
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

export default MainLayout;

