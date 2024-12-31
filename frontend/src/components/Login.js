import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    TextField,
    Button,
    Box,
    Typography,
    Alert,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
} from '@mui/material';

function Login({ onLoginSuccess }) {
    const API_URL = process.env.REACT_APP_API_URL;
    const navigate = useNavigate(); // Use navigate hook

    const [formData, setFormData] = useState({
        username: '',
        password: '',
    });
    const [error, setError] = useState(null);
    const [openForgotPassword, setOpenForgotPassword] = useState(false);
    const [email, setEmail] = useState('');
    const [resetError, setResetError] = useState(null);
    const [resetSuccess, setResetSuccess] = useState(null);

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);

        try {
            const response = await fetch(`${API_URL}/api/auth/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            if (response.ok) {
                const data = await response.json();
                onLoginSuccess(data); // Set authentication state
                navigate('/chat'); // Redirect to chat page
            } else {
                const errorData = await response.json();
                console.log(errorData.error);
                // Check if the error message contains specific details
                if (errorData.error) {
                    if (
                        errorData.error.includes('username') ||
                        errorData.error.includes('email')
                    ) {
                        setError(
                            'Username or email is incorrect. Please check and try again.'
                        );
                    } else if (errorData.error.includes('password')) {
                        setError('Password is incorrect. Please try again.');
                    } else {
                        setError(errorData.error); // If it's a generic error message
                    }
                } else {
                    setError('Login failed. Please try again.');
                }
            }
        } catch (err) {
            setError('An error occurred. Please check your connection.');
        }
    };

    const handleForgotPasswordSubmit = async (e) => {
        e.preventDefault();
        setResetError(null);
        setResetSuccess(null);

        try {
            const response = await fetch(
                `${API_URL}/api/auth/forgot-password/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email }),
                }
            );

            if (response.ok) {
                setResetSuccess(
                    'A password reset link has been sent to your email.'
                );
            } else {
                const errorData = await response.json();
                setResetError(
                    errorData.detail ||
                        'Password reset failed. Please try again.'
                );
            }
        } catch (err) {
            setResetError('An error occurred. Please check your connection.');
        }
    };

    return (
        <>
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                    backgroundColor: '#f5f5f5',
                }}
            >
                <Box
                    sx={{
                        maxWidth: 400,
                        width: '100%',
                        padding: 3,
                        boxShadow: 3,
                        borderRadius: 2,
                        backgroundColor: 'white',
                    }}
                >
                    <Typography variant='h4' gutterBottom align='center'>
                        Login
                    </Typography>
                    {error && <Alert severity='error'>{error}</Alert>}
                    <form onSubmit={handleSubmit}>
                        <TextField
                            name='username'
                            label='Username'
                            variant='outlined'
                            fullWidth
                            margin='normal'
                            value={formData.username}
                            onChange={handleChange}
                        />
                        <TextField
                            name='password'
                            label='Password'
                            type='password'
                            variant='outlined'
                            fullWidth
                            margin='normal'
                            value={formData.password}
                            onChange={handleChange}
                        />
                        <Button
                            type='submit'
                            variant='contained'
                            color='primary'
                            fullWidth
                            sx={{ mt: 2 }}
                        >
                            Login
                        </Button>
                    </form>
                    <Typography align='center' sx={{ mt: 2 }}>
                        Don't have an account?{' '}
                        <Button
                            variant='text'
                            onClick={() => navigate('/signup')}
                        >
                            Signup
                        </Button>
                    </Typography>
                    <Typography align='center' sx={{ mt: 2 }}>
                        <Button
                            variant='text'
                            onClick={() => setOpenForgotPassword(true)}
                        >
                            Forgot Password?
                        </Button>
                    </Typography>
                </Box>
            </Box>

            {/* Forgot Password Dialog */}
            <Dialog
                open={openForgotPassword}
                onClose={() => setOpenForgotPassword(false)}
            >
                <DialogTitle>Forgot Password</DialogTitle>
                <DialogContent>
                    <Typography variant='body1' gutterBottom>
                        Enter your email address, and we'll send you a password
                        reset link.
                    </Typography>
                    {resetError && <Alert severity='error'>{resetError}</Alert>}
                    {resetSuccess && (
                        <Alert severity='success'>{resetSuccess}</Alert>
                    )}
                    <TextField
                        label='Email'
                        variant='outlined'
                        fullWidth
                        margin='normal'
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button
                        onClick={() => setOpenForgotPassword(false)}
                        color='primary'
                    >
                        Cancel
                    </Button>
                    <Button
                        onClick={handleForgotPasswordSubmit}
                        color='primary'
                        variant='contained'
                    >
                        Submit
                    </Button>
                </DialogActions>
            </Dialog>
        </>
    );
}

export default Login;
