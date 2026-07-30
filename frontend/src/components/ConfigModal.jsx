import React from 'react';
import { Sliders } from 'lucide-react';

export default function ConfigModal({ 
  isOpen, 
  onClose, 
  topK, 
  setTopK, 
  apiHealth
}) {
  if (!isOpen) return null;

  const isOnline = apiHealth?.status === 'ok';

  return (
    <>
      {/* Global Backdrop to capture outside clicks */}
      <div 
        className="fixed inset-0 z-[9998] bg-transparent" 
        onClick={onClose} 
      />

      {/* Floating Config Dropdown Card */}
      <div 
        className="fixed top-20 right-6 sm:right-8 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl p-5 border border-orange-500/20 z-[9999] animate-fade-in text-stone-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="space-y-4">
          {/* Header */}
          <div className="flex justify-between items-center pb-2 border-b border-orange-500/15">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-orange-600" />
              <span className="text-xs font-bold uppercase tracking-wider text-stone-700">Retrieval Config</span>
            </div>
            
            <div className={`px-2.5 py-1 rounded-full border flex items-center gap-1.5 text-xs font-semibold ${
              isOnline 
                ? 'bg-orange-500/10 border-orange-500/20 text-orange-600' 
                : 'bg-rose-500/10 border-rose-500/20 text-rose-600'
            }`}>
              <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-orange-500 animate-pulse' : 'bg-rose-500'}`}></span>
              <span>{isOnline ? 'Online' : 'Offline'}</span>
            </div>
          </div>

          {/* Top-K Slider */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-medium text-stone-600">
              <span>Top-K Sources Retrieved</span>
              <span className="text-xs font-mono font-bold bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded-md text-orange-600">
                {topK}
              </span>
            </div>
            <input 
              type="range" 
              min="1" 
              max="10" 
              value={topK} 
              onChange={(e) => setTopK(parseInt(e.target.value, 10))}
              className="w-full accent-orange-500 cursor-pointer bg-stone-200 h-1.5 rounded-lg"
            />
            <p className="text-[11px] text-stone-500 leading-tight">
              Adjust maximum number of relevant statutory chunks returned per query.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
