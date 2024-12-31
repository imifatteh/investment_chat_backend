import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TextField, Button, Box, Typography, Alert } from '@mui/material';

function ResetPassword() {
    const { token, uid } = useParams(); // Get token and uid from URL params
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);
    const navigate = useNavigate(); // for redirecting after reset
    const API_URL = process.env.REACT_APP_API_URL;

    useEffect(() => {
        if (!token || !uid) {
            setError('Invalid reset link. Please request a new one.');
        }
    }, [token, uid]);

    const validatePassword = (password) => {
        const regex = /^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*\W).{8,}$/;
        return regex.test(password);
    };

    const handleChange = (e) => {
        if (e.target.name === 'password') {
            setPassword(e.target.value);
        } else if (e.target.name === 'confirmPassword') {
            setConfirmPassword(e.target.value);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);

        // Validate passwords before submitting
        if (!validatePassword(password)) {
            setError(
                'Password must be at least 8 characters long, include a number, an uppercase letter, and a special character.'
            );
            return;
        }

        if (password !== confirmPassword) {
            setError('Passwords do not match. Please try again.');
            return;
        }

        try {
            const response = await fetch(
                `${API_URL}/api/auth/reset-password/${uid}/${token}/`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        new_password: password,
                    }),
                }
            );

            if (response.ok) {
                setSuccess(true);
                setTimeout(() => {
                    navigate('/login'); // Redirect to login after successful reset
                }, 3000); // Timeout for 3 seconds
            } else {
                const errorData = await response.json();
                setError(
                    errorData.detail ||
                        'Password reset failed. Please try again.'
                );
            }
        } catch (err) {
            setError('An error occurred. Please check your connection.');
        }
    };

    return (
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
                    Reset Password
                </Typography>
                {error && <Alert severity='error'>{error}</Alert>}
                {success && (
                    <Alert severity='success'>
                        Password reset successful! Redirecting...
                    </Alert>
                )}
                <form onSubmit={handleSubmit}>
                    <TextField
                        label='New Password'
                        type='password'
                        variant='outlined'
                        fullWidth
                        margin='normal'
                        value={password}
                        onChange={handleChange}
                        name='password'
                        required
                        error={error && error.includes('Password must be')}
                        helperText={
                            error &&
                            error.includes('Password must be') &&
                            'Password must be at least 8 characters long, include a number, an uppercase letter, and a special character.'
                        }
                    />
                    <TextField
                        label='Confirm Password'
                        type='password'
                        variant='outlined'
                        fullWidth
                        margin='normal'
                        value={confirmPassword}
                        onChange={handleChange}
                        name='confirmPassword'
                        required
                        error={
                            error && error.includes('Passwords do not match')
                        }
                        helperText={
                            error &&
                            error.includes('Passwords do not match') &&
                            'Passwords must be the same.'
                        }
                    />
                    <Button
                        type='submit'
                        variant='contained'
                        color='primary'
                        fullWidth
                        sx={{ mt: 2 }}
                    >
                        Reset Password
                    </Button>
                </form>
            </Box>
        </Box>
    );
}

export default ResetPassword;
