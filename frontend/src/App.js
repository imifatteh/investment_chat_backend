import React, { useState, useEffect } from 'react';
import {
    BrowserRouter as Router,
    Route,
    Routes,
    Navigate,
} from 'react-router-dom';
import './App.css';
import Chat from './components/Chat';
import SignupForm from './components/SignupForm';
import Login from './components/Login';
import ResetPassword from './components/ResetPassword';
import Header from './components/Header';

function App() {
    const [isAuthenticated, setIsAuthenticated] = useState(
        !!localStorage.getItem('accessToken')
    );
    const [user, setUser] = useState(
        JSON.parse(localStorage.getItem('user')) || null
    );

    const handleSignupSuccess = () => {
        setIsAuthenticated(true);
    };

    const handleLoginSuccess = (data) => {
        setIsAuthenticated(true);
        setUser(data.user);
        localStorage.setItem('accessToken', data.access);
        localStorage.setItem('user', JSON.stringify(data.user));
    };

    const handleLogout = () => {
        setIsAuthenticated(false);
        setUser(null);
        localStorage.removeItem('accessToken');
        localStorage.removeItem('user');
    };

    useEffect(() => {
        const storedToken = localStorage.getItem('accessToken');
        const storedUser = localStorage.getItem('user');
        if (storedToken && storedUser) {
            setIsAuthenticated(true);
            setUser(JSON.parse(storedUser));
        } else {
            setIsAuthenticated(false);
            setUser(null);
        }
    }, []);

    return (
        <Router>
            <div className='App'>
                <Header
                    isAuthenticated={isAuthenticated}
                    user={user}
                    onLogout={handleLogout}
                />{' '}
                {/* Header is back! */}
                <Routes>
                    <Route
                        path='/'
                        element={
                            <Navigate
                                to={isAuthenticated ? '/chat' : '/login'}
                            />
                        }
                    />
                    <Route
                        path='/login'
                        element={<Login onLoginSuccess={handleLoginSuccess} />}
                    />
                    <Route
                        path='/signup'
                        element={
                            <SignupForm onSignupSuccess={handleSignupSuccess} />
                        }
                    />
                    <Route
                        path='/reset-password/:uid/:token'
                        element={<ResetPassword />}
                    />
                    <Route
                        path='/chat'
                        element={
                            isAuthenticated ? (
                                <Chat />
                            ) : (
                                <Navigate to='/login' />
                            )
                        }
                    />
                </Routes>
            </div>
        </Router>
    );
}

export default App;
