import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import Home from './Home';
import { AuthProvider } from '../contexts/AuthContext';

describe('Home', () => {
    it('should render home page with main heading', () => {
        render(
            <BrowserRouter>
                <AuthProvider>
                    <Home />
                </AuthProvider>
            </BrowserRouter>
        );

        expect(
            screen.getByRole('heading', { level: 1, name: /Bridging Villages with Intelligent Action/i })
        ).toBeInTheDocument();
    });

    it('should render call-to-action buttons', () => {
        render(
            <BrowserRouter>
                <AuthProvider>
                    <Home />
                </AuthProvider>
            </BrowserRouter>
        );

        expect(screen.getByText(/Start Volunteering/i)).toBeInTheDocument();
        expect(screen.getByText(/Explore Projects/i)).toBeInTheDocument();
    });

    it('should render features section', () => {
        const { container } = render(
            <BrowserRouter>
                <AuthProvider>
                    <Home />
                </AuthProvider>
            </BrowserRouter>
        );

        // Check that features section exists by ID
        const featuresSection = container.querySelector('#features');
        expect(featuresSection).toBeInTheDocument();

        // Verify it has content
        expect(featuresSection).not.toBeEmptyDOMElement();
    });
});
