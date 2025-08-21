import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// Função simples para renderizar markdown básico
const renderMarkdown = (text) => {
  const html = text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^#{3}\s(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2}\s(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#{1}\s(.+)$/gm, '<h1>$1</h1>')
    .replace(/^\*\s(.+)$/gm, '<li>$1</li>')
    .replace(/(\n<li>.*<\/li>\n)/gs, '<ul>$1</ul>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');

  return { __html: html };
};

function App() {
  const [theme, setTheme] = useState(localStorage.getItem('chat-theme') || 'light');
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Olá! Sou seu assistente de testes. Digite ou fale sua mensagem.' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [gravando, setGravando] = useState(false);

  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);

  useEffect(() => {
    document.body.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('chat-theme', theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleTheme = () => {
    setTheme(prevTheme => (prevTheme === 'light' ? 'dark' : 'light'));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { from: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch('http://localhost:8000/webhook/webchat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texto: input,
          sessao_id: 'local-dev-user'
        }),
      });

      const data = await response.json();
      setMessages(prev => [...prev, { from: 'bot', text: data.conteudo_markdown }]);

    } catch (error) {
      console.error("Erro ao enviar mensagem:", error);
      setMessages(prev => [...prev, { from: 'bot', text: 'Erro de conexão com backend.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const gravarAudio = async () => {
    if (gravando) {
      mediaRecorderRef.current.stop();
      setGravando(false);
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      alert("Seu navegador não suporta gravação de áudio.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];

      mediaRecorder.ondataavailable = (e) => {
        chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio', blob, 'audio.webm');

        setIsTyping(true);
        try {
          const response = await fetch('/webchat/audio', {
            method: 'POST',
            body: formData,
          });

          const data = await response.json();
          setMessages(prev => [...prev, { from: 'bot', text: data.conteudo_markdown }]);

        } catch (error) {
          console.error("Erro ao enviar áudio:", error);
          setMessages(prev => [...prev, { from: 'bot', text: 'Erro ao processar áudio.' }]);
        } finally {
          setIsTyping(false);
        }
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setGravando(true);

    } catch (err) {
      console.error("Erro ao acessar microfone:", err);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h3>Chat de Teste</h3>
        <button onClick={toggleTheme} className="theme-toggle">
          Mudar para tema {theme === 'light' ? 'Escuro' : 'Claro'}
        </button>
      </div>

      <div className="chat-window">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.from}`}>
            {msg.from === 'bot' ? (
              <div className="markdown-content" dangerouslySetInnerHTML={renderMarkdown(msg.text)} />
            ) : (
              <p>{msg.text}</p>
            )}
          </div>
        ))}
        {isTyping && (
          <div className="message bot typing">
            <p><span>.</span><span>.</span><span>.</span></p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSend} className="chat-input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Digite sua mensagem..."
          autoFocus
        />
        <button type="submit">Enviar</button>
        <button type="button" onClick={gravarAudio}>
          {gravando ? 'Parar' : '🎤 Gravar'}
        </button>
      </form>
    </div>
  );
}

export default App;
