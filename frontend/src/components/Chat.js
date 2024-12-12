import React from 'react';
import Chart from './Chart';

function Chat() {
    const [messages, setMessages] = React.useState([]);
    const [inputMessage, setInputMessage] = React.useState('');

    const sendMessage = async () => {
        if (!inputMessage.trim()) return;

        const newMessages = [
            ...messages,
            { type: 'user', content: inputMessage },
        ];
        setMessages(newMessages);
        setInputMessage('');

        try {
            const API_URL = process.env.REACT_APP_API_URL;
            const response = await fetch(`${API_URL}/process_message/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // 'X-CSRFToken': document.querySelector(
                    //     '[name=csrfmiddlewaretoken]'
                    // ).value,
                },
                body: JSON.stringify({ message: inputMessage }),
            });

            const data = await response.json();
            if (data && data.response) {
                setMessages([
                    ...newMessages,
                    { type: 'ai', content: data.response },
                ]);
            }
        } catch (error) {
            console.error('Error:', error);
            setMessages([
                ...newMessages,
                { type: 'error', content: 'Failed to get response' },
            ]);
        }
    };
    return (
        <>
            <div className='h-screen flex flex-col'>
                <header className='bg-blue-600 p-4 text-white'>
                    <h1 className='text-xl font-bold'>
                        Investment Chat Analysis
                    </h1>
                </header>

                <div className='flex-1 flex'>
                    {/* Left Panel - Chat */}
                    <div className='w-1/2 p-4 flex flex-col'>
                        <div className='flex-1 border rounded-lg p-4 overflow-y-auto mb-4'>
                            {messages.map((msg, index) => (
                                <div key={index} className='mb-2'>
                                    <strong
                                        className={
                                            msg.type === 'user'
                                                ? 'text-blue-600'
                                                : 'text-green-600'
                                        }
                                    >
                                        {msg.type === 'user' ? 'You: ' : 'AI: '}
                                    </strong>
                                    <span>{msg.content}</span>
                                </div>
                            ))}
                        </div>

                        <div className='flex gap-2'>
                            <input
                                type='text'
                                value={inputMessage}
                                onChange={(e) =>
                                    setInputMessage(e.target.value)
                                }
                                onKeyPress={(e) =>
                                    e.key === 'Enter' && sendMessage()
                                }
                                className='flex-1 p-2 border rounded'
                                placeholder='Type your message...'
                            />
                            <button
                                onClick={sendMessage}
                                className='bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700'
                            >
                                Send
                            </button>
                        </div>
                    </div>

                    {/* Right Panel - Future Dashboard */}
                    <div className='w-1/2 p-4'>
                        <div className='h-full border rounded-lg p-4 flex items-center justify-center text-gray-500'>
                            <Chart ticker='DJIA' />
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

export default Chat;
