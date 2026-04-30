import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import { AuthProvider } from './app/providers/AuthProvider';
import { ThemeProvider } from './app/providers/ThemeProvider';
import { router } from './app/router';
import './styles/globals.css';
import './styles/theme.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <RouterProvider
          router={router}
          future={{
            v7_startTransition: true
          }}
        />
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>
);
