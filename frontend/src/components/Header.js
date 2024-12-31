import React from 'react';
import { useNavigate } from 'react-router-dom';

function Header({ isAuthenticated, user, onLogout }) {
    const navigate = useNavigate();

    const handleLogoutClick = () => {
        onLogout();
        navigate('/'); // Redirect to home page after logout
    };

    return (
        <header className='bg-blue-600 p-4 text-white flex justify-between items-center'>
            <h1 className='text-xl font-bold'>Investment Chat Analysis</h1>
            {isAuthenticated && user ? (
                <div className='flex items-center space-x-4'>
                    <span>
                        Welcome, <strong>{user.username}</strong>
                    </span>
                    <button
                        onClick={handleLogoutClick}
                        className='bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded'
                    >
                        Logout
                    </button>
                </div>
            ) : null}
        </header>
    );
}

export default Header;
