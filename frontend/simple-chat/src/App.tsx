import Chat from './components/Chat'

function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <h1 className="text-2xl font-bold text-center mb-4 text-blue-700">
          Banking Assistant
        </h1>
        <Chat />
      </div>
    </div>
  )
}

export default App
