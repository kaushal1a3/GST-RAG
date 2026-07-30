import React from 'react';
import { BookOpen, ShieldCheck, Zap, X, Cpu, Layers } from 'lucide-react';

export default function AboutModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-stone-900/40 backdrop-blur-sm animate-fade-in">
      <div 
        className="w-full max-w-xl bg-white rounded-2xl border border-orange-500/20 shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-5 bg-gradient-to-r from-orange-500/10 via-amber-500/5 to-transparent border-b border-orange-500/15 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center text-white shadow-md shadow-orange-500/20">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="display-font text-lg font-bold text-stone-900">About Ask GST RAG</h3>
              <p className="text-xs text-stone-500 font-medium">Grounded Legal Tax Intelligence System</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-600 flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5 text-sm text-stone-700 leading-relaxed overflow-y-auto max-h-[70vh]">
          <p>
            <strong className="font-semibold text-stone-900">Ask GST RAG</strong> is an AI-powered legal retrieval and generation engine designed for navigating complex Indian Goods and Services Tax (GST) law.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div className="glass-card p-4 rounded-xl border border-orange-500/15 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-orange-600 font-semibold text-xs">
                <ShieldCheck className="w-4 h-4" />
                <span>Zero Hallucination Grounding</span>
              </div>
              <p className="text-xs text-stone-600">
                Answers are grounded with verifiable statutory citations directly from CGST, IGST, UTGST Acts & Rules.
              </p>
            </div>

            <div className="glass-card p-4 rounded-xl border border-orange-500/15 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-amber-600 font-semibold text-xs">
                <Zap className="w-4 h-4" />
                <span>Hybrid BM25 + Vector Retrieval</span>
              </div>
              <p className="text-xs text-stone-600">
                Combines BGE-Small dense embeddings with BM25 keyword matching for high recall & precision.
              </p>
            </div>

            <div className="glass-card p-4 rounded-xl border border-orange-500/15 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-orange-700 font-semibold text-xs">
                <Cpu className="w-4 h-4" />
                <span>LLM Query Router</span>
              </div>
              <p className="text-xs text-stone-600">
                Automatically routes conversational vs statutory queries for maximum answer speed.
              </p>
            </div>

            <div className="glass-card p-4 rounded-xl border border-orange-500/15 flex flex-col gap-2">
              <div className="flex items-center gap-2 text-amber-700 font-semibold text-xs">
                <Layers className="w-4 h-4" />
                <span>Updated Coverage</span>
              </div>
              <p className="text-xs text-stone-600">
                Based on official Acts, Rules, Notifications and Circulars up to 2026.
              </p>
            </div>
          </div>

          <div className="bg-stone-50 border border-orange-500/15 p-3.5 rounded-xl text-xs text-stone-500">
            <strong className="text-stone-700 font-semibold">Disclaimer:</strong> Information provided is for educational and research reference. Always verify against official CBIC notifications for official legal advice.
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-stone-50 border-t border-stone-200/80 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs transition-all shadow-sm"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
