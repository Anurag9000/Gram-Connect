import { describe, it, expect } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AuthProvider } from './AuthContext';
import { useAuth } from './auth-shared';

// A component that uses the auth context for testing
const TestComponent = () => {
    const { user, profile, signIn, signOut, loading } = useAuth();
    return (
        <div>
            <div data-testid="user">{user ? user.id : 'no-user'}</div>
            <div data-testid="role">{profile ? profile.role : 'villager'}</div>
            <div data-testid="loading">{loading ? 'true' : 'false'}</div>
            <button onClick={() => signIn('volunteer@test.com', 'password')}>Sign In Volunteer</button>
            <button onClick={() => signIn('coordinator@test.com', 'password')}>Sign In Coordinator</button>
            <button onClick={() => signIn('supervisor@test.com', 'password')}>Sign In Supervisor</button>
            <button onClick={() => signIn('partner@test.com', 'password')}>Sign In Partner</button>
            <button onClick={() => signOut()}>Sign Out</button>
        </div>
    );
};

describe('AuthContext', () => {
    it('should provide initial villager state', () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        expect(screen.getByTestId('user').textContent).toBe('no-user');
        expect(screen.getByTestId('role').textContent).toBe('villager');
        expect(screen.getByTestId('loading').textContent).toBe('false');
    });

    it('should sign in a volunteer', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        await act(async () => {
            screen.getByText('Sign In Volunteer').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('mock-volunteer-uuid');
        expect(screen.getByTestId('role').textContent).toBe('volunteer');
    });

    it('should sign in a coordinator', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        await act(async () => {
            screen.getByText('Sign In Coordinator').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('mock-coordinator-uuid');
        expect(screen.getByTestId('role').textContent).toBe('coordinator');
    });

    it('should sign in a supervisor', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        await act(async () => {
            screen.getByText('Sign In Supervisor').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('mock-supervisor-uuid');
        expect(screen.getByTestId('role').textContent).toBe('supervisor');
    });

    it('should sign in a partner', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        await act(async () => {
            screen.getByText('Sign In Partner').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('mock-partner-uuid');
        expect(screen.getByTestId('role').textContent).toBe('partner');
    });

    it('should sign out', async () => {
        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        );

        await act(async () => {
            screen.getByText('Sign In Volunteer').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('mock-volunteer-uuid');

        await act(async () => {
            screen.getByText('Sign Out').click();
        });

        expect(screen.getByTestId('user').textContent).toBe('no-user');
        expect(screen.getByTestId('role').textContent).toBe('villager');
    });
});
