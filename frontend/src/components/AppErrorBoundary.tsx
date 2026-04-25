import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export default class AppErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
    message: '',
  };

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      message: error.message || 'Unexpected application error',
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Application render failure:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
          <div className="w-full max-w-xl rounded-2xl border border-red-200 bg-white p-8 shadow-lg">
            <h1 className="text-2xl font-bold text-red-700">Gram Connect hit a render error</h1>
            <p className="mt-3 text-sm text-gray-600">
              The page failed to load fully in this browser session. Reload once to recover.
            </p>
            <p className="mt-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
              {this.state.message}
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="mt-6 rounded-lg bg-green-600 px-5 py-2.5 font-medium text-white hover:bg-green-700"
            >
              Reload App
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
