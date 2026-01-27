import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Navigation from './Navigation';
import { AuthProvider } from '../contexts/AuthContext';
import React from 'react';

describe('Navigation', () => {
    it('should render navigation bar', () => {
        render(
            <BrowserRouter>
                <AuthProvider>
                    <Navigation />
                </AuthProvider>
            </BrowserRouter>
        );

        expect(screen.getByText('SocialCode')).toBeInTheDocument();
    });

    it('should show login buttons when not authenticated', () => {
        render(
            <BrowserRouter>
                <AuthProvider>
                    <Navigation />
                </AuthProvider>
            </BrowserRouter>
        );

        // The buttons show "Volunteer" and "Coordinator" text (without "Login")
        expect(screen.getByText('Volunteer')).toBeInTheDocument();
        expect(screen.getByText('Coordinator')).toBeInTheDocument();
    });
});
