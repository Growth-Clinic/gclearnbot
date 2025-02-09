import React from 'react';
import { BrowserRouter as Router } from 'react-router-dom';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto py-6 px-4">
            <h1 className="text-3xl font-bold text-gray-900">
              Growth Clinic
            </h1>
          </div>
        </header>
        <main className="max-w-7xl mx-auto py-6 px-4">
          {/* Routes will go here */}
          <p className="text-gray-500">Welcome to Growth Clinic</p>
        </main>
      </div>
    </Router>
  );
}

export default App;