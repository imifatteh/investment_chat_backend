import React, { useState } from 'react';
import { TextField, Button, Box, Typography, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';

function SignupForm({ onSignupSuccess }) {
    const API_URL = process.env.REACT_APP_API_URL;
    const navigate = useNavigate();

    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
    });
    const [error, setError] = useState(null);
    const [passwordError, setPasswordError] = useState(null);
    const [signupSuccess, setSignupSuccess] = useState(false);

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value,
        });
    };

    // Password validation regex (At least 8 characters, one uppercase, one lowercase, one number, one special character)
    const validatePassword = (password) => {
        const regex = /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*\W).{8,}$/;
        return regex.test(password);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setPasswordError(null);

        // Validate password
        if (!validatePassword(formData.password)) {
            console.log("Password doesn't meet requirements");
            setPasswordError(
                'Password must be at least 8 characters long, include an uppercase letter, a number, and a special character.'
            );
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/auth/signup/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            if (response.ok) {
                setSignupSuccess(true);
                onSignupSuccess();

                // Redirect to login page after 3 seconds
                setTimeout(() => {
                    navigate('/login');
                }, 3000);
            } else {
                const errorData = await response.json();

                // Check if the error is due to duplicate email
                if (errorData.error && errorData.error.includes('email')) {
                    setError('A user with this email already exists.');
                } else {
                    // Handle other errors
                    setError(
                        errorData.detail || 'Signup failed. Please try again.'
                    );
                }
            }
        } catch (err) {
            setError('An error occurred. Please check your connection.');
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
                        Signup
                    </Typography>
                    {error && <Alert severity='error'>{error}</Alert>}
                    {passwordError && (
                        <Alert severity='error'>{passwordError}</Alert>
                    )}
                    {signupSuccess && (
                        <Alert severity='success'>
                            Signup successful! Redirecting to login page.
                        </Alert>
                    )}
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
                            name='email'
                            label='Email'
                            type='email'
                            variant='outlined'
                            fullWidth
                            margin='normal'
                            value={formData.email}
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
                            Signup
                        </Button>
                    </form>
                    <Typography align='center' sx={{ mt: 2 }}>
                        Already have an account?{' '}
                        <Button
                            variant='text'
                            onClick={() => navigate('/login')}
                        >
                            Login
                        </Button>
                    </Typography>
                </Box>
            </Box>
        </>
    );
}

export default SignupForm;
