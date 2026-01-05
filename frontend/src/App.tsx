import { useState, useEffect } from 'react';
import { UploadForm } from './components/UploadForm';
import { Dashboard } from './components/Dashboard';

function App() {
  const [taskId, setTaskId] = useState<string | null>(null);

  // Allow restoring session from localStorage or URL param (simplified for now)
  useEffect(() => {
    const savedId = localStorage.getItem('citeguard_task_id');
    if (savedId) {
      setTaskId(savedId);
    }
  }, []);

  const handleTaskCreated = (id: string) => {
    setTaskId(id);
    localStorage.setItem('citeguard_task_id', id);
  };

  const handleReset = () => {
    setTaskId(null);
    localStorage.removeItem('citeguard_task_id');
  };

  return (
    <div className="min-h-screen bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        <header className="mb-12 text-center">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">
            Cite<span className="text-blue-600">Guard</span>
          </h1>
          <p className="mt-2 text-lg text-gray-600">
            Automated Citation Verification & Context Checking
          </p>
        </header>

        <main>
          {!taskId ? (
            <UploadForm onTaskCreated={handleTaskCreated} />
          ) : (
            <Dashboard taskId={taskId} onReset={handleReset} />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
