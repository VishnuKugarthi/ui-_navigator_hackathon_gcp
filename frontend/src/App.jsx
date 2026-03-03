import { useState, useRef, useEffect } from 'react';

function App() {
  const [isCapturing, setIsCapturing] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [actionLog, setActionLog] = useState([{ status: 'Welcome', detail: 'Agent is ready. Please start capture and provide a command.' }]);
  const [provider, setProvider] = useState('gcp');
  const [isLoading, setIsLoading] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(null);

  const currentFrameRef = useRef(null);
  const pollingInterval = useRef(null);
  const recognitionRef = useRef(null);
  const isInterruptedRef = useRef(false);

  useEffect(() => {
    // Initialize Speech Recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.onresult = (event) => {
        let currentTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          currentTranscript += event.results[i][0].transcript;
        }
        setTranscript(currentTranscript);
      };
      recognition.onerror = (event) => {
        console.error('Speech recognition error', event.error);
        setIsListening(false);
      };
      recognition.onend = () => {
        setIsListening(false);
      };
      recognitionRef.current = recognition;
    } else {
      console.warn('Speech Recognition API not supported in this browser.');
    }
  }, []);

  const fetchScreenshot = async (apiUrl) => {
    try {
      const response = await fetch(`${apiUrl}/screenshot`);
      if (response.ok) {
        const data = await response.json();
        if (data.screenshot) {
          setCurrentFrame(data.screenshot);
          currentFrameRef.current = data.screenshot;
        }
      }
    } catch (err) {
      console.error("Error fetching screenshot", err);
    }
  };

  const startScreenCapture = () => {
    setIsCapturing(true);
    const apiUrl = 'http://localhost:8002';
    fetchScreenshot(apiUrl);
    pollingInterval.current = setInterval(() => fetchScreenshot(apiUrl), 500);
  };

  const stopScreenCapture = () => {
    setIsCapturing(false);
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
    }
    setCurrentFrame(null);
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      recognitionRef.current?.start();
      setIsListening(true);
    }
  };

  const captureFrame = () => {
    return currentFrameRef.current;
  };

  const submitGoal = async () => {
    if (!transcript.trim()) {
      alert("Please provide a voice command first.");
      return;
    }

    // Stop listening before processing
    if (isListening) {
      toggleListening();
    }

    setIsLoading(true);
    // Gemini Backend uses 8002
    const apiUrl = 'http://localhost:8002';

    try {
      isInterruptedRef.current = false;
      setActionLog([{ status: `Starting: ${provider.toUpperCase()}`, detail: `Goal: ${transcript}` }]);

      let isComplete = false;
      let stepCount = 0;
      const maxSteps = 10;
      let historyLogs = [];

      while (!isComplete && stepCount < maxSteps) {
        if (isInterruptedRef.current) {
          setActionLog(prev => [...prev, { status: "Interrupted", detail: "Process was stopped by user." }]);
          break;
        }
        stepCount++;

        const screenshot = captureFrame();
        if (!screenshot) {
          if (stepCount === 1) {
            alert("Please start screen capture first to extract a frame.");
            setIsLoading(false);
            return;
          } else {
            setActionLog(prev => [...prev, { status: "Error", detail: "Could not capture frame. Screen capture may have stopped." }]);
            break;
          }
        }

        setActionLog(prev => [...prev, { status: `Step ${stepCount}`, detail: `Looking at the screen to decide what to do next...` }]);

        const response = await fetch(`${apiUrl}/plan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal: transcript, screenshot, history: historyLogs })
        });

        if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
        const data = await response.json();

        setActionLog(prev => [...prev, { status: "What I See", detail: data.vision.description }]);
        setActionLog(prev => [...prev, { status: "My Decision", detail: data.plan.reasoning }]);

        if (!data.plan.steps || data.plan.steps.length === 0) {
          setActionLog(prev => [...prev, { status: "Goal Reached", detail: "I've successfully finished the task!" }]);
          isComplete = true;
          break;
        }

        for (const step of data.plan.steps) {
          historyLogs.push(`Attempted: ${step.action_type} on target ${step.target} with value ${step.value || 'None'}`);
          if (historyLogs.length > 5) historyLogs.shift();

          setActionLog(prev => [...prev, { status: "Taking Action", detail: "I'm performing the next step now..." }]);

          const execRes = await fetch(`${apiUrl}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(step)
          });

          if (!execRes.ok) throw new Error(`HTTP Error ${execRes.status}`);
          const execData = await execRes.json();

          setActionLog(prev => [...prev, { status: "Result", detail: execData.message }]);
        }

        // Wait for page to settle after actions before taking next screenshot
        if (!isComplete && !isInterruptedRef.current) {
          await new Promise(r => setTimeout(r, 2000));
        }
      }

      if (stepCount >= maxSteps && !isComplete) {
        setActionLog(prev => [...prev, { status: "Workflow Stopped", detail: "Maximum iterations reached." }]);
      } else if (isComplete) {
        setActionLog(prev => [...prev, { status: "Task Finished", detail: "I've completed everything you asked for." }]);
      }

    } catch (err) {
      console.error("Error submitting goal", err);
      setActionLog(prev => [...prev, { status: "Error", detail: err.message }]);
    } finally {
      setIsLoading(false);
    }
  };

  const interruptAgent = async () => {
    isInterruptedRef.current = true;
    setIsLoading(false);
    const apiUrl = 'http://localhost:8002';
    try {
      await fetch(`${apiUrl}/interrupt`, { method: 'POST' });
    } catch (err) {
      console.error("Failed to signal interrupt to backend", err);
    }
    setActionLog(prev => [...prev, { status: "Stopping...", detail: "Sending stop signal to agent." }]);
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-800">Agentic UI Navigator</h1>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {/* Left Panel: Screen Preview */}
        <div className="w-2/3 bg-gray-100 p-6 flex flex-col">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium text-gray-700">Live Screen Preview</h2>
            {isCapturing ? (
              <button
                onClick={stopScreenCapture}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded shadow-sm text-sm font-medium transition-colors"
              >
                Stop Capture
              </button>
            ) : (
              <button
                onClick={startScreenCapture}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded shadow-sm text-sm font-medium transition-colors"
              >
                Start Capture
              </button>
            )}
          </div>

          <div className="flex-1 bg-black border border-gray-300 rounded-lg shadow-sm flex items-center justify-center overflow-hidden relative">
            {isCapturing && currentFrame && (
              <img
                src={`data:image/jpeg;base64,${currentFrame}`}
                alt="Playwright Video Feed"
                className="max-w-full max-h-full object-contain relative z-10"
              />
            )}
            {isCapturing && !currentFrame && (
              <div className="text-white text-sm z-0">Waiting for browser feed...</div>
            )}
            {!isCapturing && (
              <div className="text-center text-gray-400 absolute">
                <svg className="mx-auto h-12 w-12 mb-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <p>No screen capture shared.</p>
                <p className="text-xs mt-1">Click "Start Capture" to begin</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Agent Dashboard */}
        <div className="w-1/3 bg-white border-l border-gray-200 flex flex-col">
          {/* Voice Input Section */}
          <div className="p-4 border-b border-gray-200 bg-gray-50 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-700">Voice Command</h3>
              <button
                onClick={toggleListening}
                className={`text-sm font-medium flex items-center transition-colors ${isListening ? 'text-red-500 hover:text-red-600' : 'text-blue-500 hover:text-blue-600'
                  }`}
              >
                <span className="mr-1">{isListening ? '●' : '▶'}</span>
                {isListening ? 'Stop' : 'Start'} Listening
              </button>
            </div>
            <div className="bg-white border border-gray-300 rounded p-3 min-h-[80px] max-h-[150px] text-sm text-gray-600 italic overflow-y-auto mb-3">
              {transcript || 'Listening for commands...'}
            </div>
            <button
              onClick={submitGoal}
              disabled={isLoading || !isCapturing || !transcript.trim()}
              className={`w-full py-2 rounded shadow-sm text-sm font-medium transition-colors ${isLoading || !isCapturing || !transcript.trim() ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
            >
              {isLoading ? 'Working on it...' : 'Start Agent'}
            </button>
          </div>

          {/* Reasoning & Actions Log */}
          <div className="flex-1 p-4 overflow-y-auto bg-white">
            <h3 className="font-medium text-gray-700 mb-3">Agent Progress Log</h3>

            <div className="space-y-4">
              {actionLog.map((log, index) => (
                <div key={index} className="flex items-start">
                  <div className="mt-1 mr-3 flex-shrink-0">
                    <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse"></div>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-800">{log.status}</p>
                    <p className="text-xs text-gray-500 mt-1">{log.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end space-x-3">
            <button
              onClick={interruptAgent}
              disabled={!isLoading}
              className={`px-4 py-2 rounded text-sm font-medium transition-colors ${!isLoading ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-red-100 text-red-700 hover:bg-red-200'}`}
            >
              Interrupt Agent
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
