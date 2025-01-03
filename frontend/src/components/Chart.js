import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';

function Chart() {
    const svgRef = useRef(null);
    const [data, setData] = useState([]);
    const [searchTicker, setSearchTicker] = useState('');
    const [selectedTicker, setSelectedTicker] = useState('DJIA');
    const [timePeriod, setTimePeriod] = useState('1M'); // Default to 1 Month
    const API_URL = process.env.REACT_APP_API_URL;

    // Fetch stock data with authentication
    useEffect(() => {
        if (!selectedTicker) return;

        const fetchData = async () => {
            const token = localStorage.getItem('accessToken'); // Fetch token from localStorage

            try {
                let response = await fetch(
                    `${API_URL}/api/aggs_data/${selectedTicker}/?time_range=${timePeriod}`,
                    {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: `Bearer ${token}`,
                        },
                    }
                );

                if (response.status === 401) {
                    // Handle token expiration: attempt to refresh
                    const refreshToken = localStorage.getItem('refresh_token');
                    const refreshResponse = await fetch(
                        `${API_URL}/api/token/refresh/`,
                        {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ refresh: refreshToken }),
                        }
                    );

                    if (refreshResponse.ok) {
                        const newTokens = await refreshResponse.json();
                        localStorage.setItem('accessToken', newTokens.access);
                        localStorage.setItem(
                            'refresh_token',
                            newTokens.refresh
                        );

                        // Retry original request with new token
                        response = await fetch(
                            `${API_URL}/api/aggs_data/${selectedTicker}/?time_range=${timePeriod}`,
                            {
                                method: 'GET',
                                headers: {
                                    'Content-Type': 'application/json',
                                    Authorization: `Bearer ${newTokens.access_token}`,
                                },
                            }
                        );
                    } else {
                        throw new Error(
                            'Session expired. Please log in again.'
                        );
                    }
                }

                if (response.status === 403) {
                    throw new Error(
                        'Access denied. Please check your permissions.'
                    );
                }

                const responseData = await response.json();
                setData(responseData.data || []);
            } catch (error) {
                console.error('Error fetching data:', error.message);
                if (error.message.includes('Session expired')) {
                    alert(error.message);
                    localStorage.clear();
                    window.location.href = '/login'; // Redirect to login page
                }
            }
        };

        fetchData();
    }, [API_URL, selectedTicker, timePeriod]);

    // Render chart using D3
    useEffect(() => {
        if (data.length === 0) return;

        const svg = d3
            .select(svgRef.current)
            .attr('width', 800)
            .attr('height', 400);

        svg.selectAll('*').remove(); // Clear previous content

        const margin = { top: 20, right: 30, bottom: 40, left: 40 };
        const width = +svg.attr('width') - margin.left - margin.right;
        const height = +svg.attr('height') - margin.top - margin.bottom;

        const x = d3
            .scaleTime()
            .domain(d3.extent(data, (d) => new Date(d.t))) // Using the timestamp 't'
            .range([0, width]);

        const y = d3
            .scaleLinear()
            .domain([d3.min(data, (d) => d.l), d3.max(data, (d) => d.h)]) // Using 'l' for low and 'h' for high
            .range([height, 0]);

        svg.append('g')
            .attr(
                'transform',
                `translate(${margin.left},${height + margin.top})`
            )
            .call(d3.axisBottom(x));

        svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`)
            .call(d3.axisLeft(y));

        const line = d3
            .line()
            .x((d) => x(new Date(d.t))) // Using the timestamp 't'
            .y((d) => y(d.c)); // Using 'c' for closing price

        svg.append('path')
            .data([data])
            .attr('class', 'line')
            .attr('transform', `translate(${margin.left},${margin.top})`)
            .attr('d', line)
            .attr('fill', 'none')
            .attr('stroke', 'steelblue')
            .attr('stroke-width', 1.5);
    }, [data]);

    const handleSearchChange = (event) => {
        setSearchTicker(event.target.value.toUpperCase());
    };

    const handleSearchSubmit = (event) => {
        event.preventDefault();
        if (searchTicker) {
            setSelectedTicker(searchTicker);
        } else {
            alert('Please enter a valid ticker symbol');
        }
    };

    const handleTimePeriodChange = (event) => {
        setTimePeriod(event.target.value);
    };

    return (
        <div className='flex flex-col items-center min-h-screen'>
            <div className='w-full max-w-4xl p-4'>
                <h2 className='text-center text-xl font-bold mb-4'>
                    Stock Price Chart for {selectedTicker || 'Select a Ticker'}
                </h2>

                {/* Search Bar */}
                <div className='mb-4'>
                    <form onSubmit={handleSearchSubmit}>
                        <label
                            htmlFor='search-ticker'
                            className='mr-2 font-semibold'
                        >
                            Enter Ticker:
                        </label>
                        <input
                            type='text'
                            id='search-ticker'
                            value={searchTicker}
                            onChange={handleSearchChange}
                            className='border px-2 py-1 rounded'
                            placeholder='Enter ticker symbol (e.g., AAPL)'
                        />
                        <button
                            type='submit'
                            className='ml-2 px-4 py-1 bg-blue-500 text-white rounded'
                        >
                            Search
                        </button>
                    </form>
                </div>

                {/* Time Filter */}
                <div className='mb-4'>
                    <label htmlFor='time-period' className='mr-2 font-semibold'>
                        Select Time Period:
                    </label>
                    <select
                        id='time-period'
                        value={timePeriod}
                        onChange={handleTimePeriodChange}
                        className='border px-2 py-1 rounded'
                    >
                        <option value='1D'>1 Day</option>
                        <option value='1W'>1 Week</option>
                        <option value='1M'>1 Month</option>
                        <option value='3M'>3 Months</option>
                        <option value='6M'>6 Months</option>
                        <option value='1Y'>1 Year</option>
                    </select>
                </div>

                {/* SVG for Chart */}
                {selectedTicker && (
                    <svg ref={svgRef} className='w-full h-96 border'></svg>
                )}
            </div>
        </div>
    );
}

export default Chart;
