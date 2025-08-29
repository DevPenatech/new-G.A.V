import React, { useState, useEffect, useRef } from 'react';
import './App.css';

// --- Config de backend ---
// 1) defina REACT_APP_API_URL no .env do React (ex.: http://localhost:8000)
// 2) ou use "proxy" no package.json e chame apenas "/chat"
const API_URL =
  process.env.REACT_APP_API_URL?.replace(/\/$/, '') ||
  ''; // vazio => usará fetch relativo, requer "proxy" no package.json

// Renderizador Markdown básico (simples)
const renderMarkdown = (text) => {
  const safe = String(text ?? '')
    // transforma "\n" escapado em quebra real
    .replace(/\\n/g, '\n')

  const html = safe
    .replace(/&/g, '&amp;') // escape básico
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    // títulos
    .replace(/^#{3}\s(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#{2}\s(.+)$/gm, '<h2>$1</h2>')
    .replace(/^#{1}\s(.+)$/gm, '<h1>$1</h1>')
    // bold/italico
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // code inline
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // listas simples por linha começando com "- " ou "* "
    .replace(/^(?:-|\*)\s(.+)$/gm, '<li>$1</li>')
    .replace(/(?:<li>.*<\/li>\s*)+/g, (m) => `<ul>${m}</ul>`)
    // quebras de linha
    .replace(/\n/g, '<br/>');

  return { __html: html };
};

function App() {
  const [theme, setTheme] = useState(localStorage.getItem('chat-theme') || 'light');
  const [messages, setMessages] = useState([
    { from: 'bot', text: 'Olá! Sou seu assistente de testes. Digite sua mensagem.' }
  ]);
  const [input, setInput] = useState('');
  const [inputSessao, setInputSessao] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [gravando, setGravando] = useState(false);

  const messagesEndRef = useRef(null);
  const mediaRecorderRef = useRef(null);

  useEffect(() => {
    document.body.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('chat-theme', theme);
  }, [theme]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const texto = input.trim();
    if (!texto) return;

    const userMessage = { from: 'user', text: texto };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Se API_URL === '' usamos caminho relativo (requer proxy no package.json)
      const url = `${API_URL}/chat`;
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          texto,
          sessao_id: inputSessao
        })
      });

      // Falha HTTP?
      if (!resp.ok) {
        const errTxt = await resp.text();
        throw new Error(`HTTP ${resp.status} - ${errTxt}`);
      }

      const data = await resp.json();
      // o backend pode devolver "mensagem" OU "conteudo_markdown"
      const reply =
        data?.mensagem ??
        data?.conteudo_markdown ??
        data?.text ??
        '(sem resposta)';

      setMessages((prev) => [...prev, { from: 'bot', text: String(reply) }]);
    } catch (err) {
      console.error('Erro ao enviar mensagem:', err);
      setMessages((prev) => [
        ...prev,
        { from: 'bot', text: 'Erro de conexão com backend.' }
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const gravarAudio = async () => {
    // mantém, mas o endpoint /webchat/audio precisa existir no backend
    if (gravando) {
      mediaRecorderRef.current?.stop();
      setGravando(false);
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      alert('Seu navegador não suporta gravação de áudio.');
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
          const url = `${API_URL}/webchat/audio`;
          const resp = await fetch(url, {
            method: 'POST',
            body: formData
          });

          if (!resp.ok) {
            const errTxt = await resp.text();
            throw new Error(`HTTP ${resp.status} - ${errTxt}`);
          }

          const data = await resp.json();
          const reply =
            data?.mensagem ??
            data?.conteudo_markdown ??
            data?.text ??
            '(sem resposta de áudio)';
          setMessages((prev) => [...prev, { from: 'bot', text: String(reply) }]);
        } catch (error) {
          console.error('Erro ao enviar áudio:', error);
          setMessages((prev) => [...prev, { from: 'bot', text: 'Erro ao processar áudio.' }]);
        } finally {
          setIsTyping(false);
        }
      };

      mediaRecorder.start();
      mediaRecorderRef.current = mediaRecorder;
      setGravando(true);
    } catch (err) {
      console.error('Erro ao acessar microfone:', err);
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
      <div className="chat-header">
          <input
            type="text"
            className="chat-input"
            value={inputSessao}
            onChange={(e) => setInputSessao(e.target.value)}
            placeholder="Digite ID de sessão."
            autoFocus
          />
      </div>

      <div className="chat-window">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.from}`}>
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
        {/*<button type="button" onClick={gravarAudio}>
          {gravando ? 'Parar' : '🎤 Gravar'}
        </button>*/}
      </form>
    </div>
  );
}

export default App;
