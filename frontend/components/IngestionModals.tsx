import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Github, UploadCloud, Loader2, Search } from 'lucide-react';
import { api } from '@/lib/api';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
}

export function GithubModal({ isOpen, onClose, onSubmit }: ModalProps) {
  const [repos, setRepos] = useState<any[]>([]);
  const [filteredRepos, setFilteredRepos] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [selectedRepoUrl, setSelectedRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingRepos, setFetchingRepos] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      fetchRepos();
    }
  }, [isOpen]);

  const fetchRepos = async () => {
    setFetchingRepos(true);
    setError('');
    try {
      const res = await api.github.listRepos();
      if (res && res.repositories) {
        setRepos(res.repositories);
        setFilteredRepos(res.repositories);
      }
    } catch (err: any) {
      setError("Please sign in with GitHub first to list your repositories.");
    } finally {
      setFetchingRepos(false);
    }
  };

  useEffect(() => {
    if (search) {
      setFilteredRepos(repos.filter(r => r.full_name.toLowerCase().includes(search.toLowerCase())));
    } else {
      setFilteredRepos(repos);
    }
  }, [search, repos]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepoUrl) return;
    setError('');
    setLoading(true);
    try {
      await onSubmit({ url: selectedRepoUrl, branch: 'main' });
      setSelectedRepoUrl('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="bg-white border border-slate-200 rounded-2xl p-6 w-full max-w-2xl shadow-2xl relative max-h-[80vh] flex flex-col"
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-900 transition-colors"
            >
              <X size={20} />
            </button>
            
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600">
                <Github size={20} />
              </div>
              <h2 className="text-xl font-semibold text-slate-900">Select GitHub Repository</h2>
            </div>

            <div className="mb-4 relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search size={18} className="text-slate-400" />
              </div>
              <input 
                type="text" 
                placeholder="Search repositories..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && <p className="text-red-500 text-sm mb-4 bg-red-50 p-3 rounded-lg">{error}</p>}

            <div className="flex-1 overflow-y-auto mb-4 pr-2 space-y-2 min-h-[200px]">
              {fetchingRepos ? (
                <div className="flex items-center justify-center h-full text-slate-500">
                  <Loader2 className="animate-spin mr-2" size={24} />
                  Loading repositories...
                </div>
              ) : filteredRepos.length === 0 ? (
                <div className="text-center text-slate-500 mt-10">
                  No repositories found.
                </div>
              ) : (
                filteredRepos.map(repo => (
                  <div 
                    key={repo.id}
                    onClick={() => setSelectedRepoUrl(repo.clone_url)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all flex justify-between items-center ${selectedRepoUrl === repo.clone_url ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50'}`}
                  >
                    <div>
                      <h4 className="font-medium text-slate-900">{repo.full_name}</h4>
                      {repo.description && <p className="text-xs text-slate-500 mt-1 truncate max-w-md">{repo.description}</p>}
                    </div>
                    {repo.private && (
                      <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded-full">Private</span>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">Or paste public repository URL:</label>
              <input
                type="url"
                placeholder="https://github.com/username/repo"
                className="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2 text-slate-900 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all shadow-sm"
                value={selectedRepoUrl}
                onChange={(e) => setSelectedRepoUrl(e.target.value)}
              />
            </div>

            <div className="pt-4 border-t border-slate-100 flex justify-end gap-3 mt-auto">
              <button
                onClick={onClose}
                className="px-4 py-2 text-slate-600 font-medium hover:bg-slate-100 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={loading || !selectedRepoUrl}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium px-6 py-2 rounded-lg transition-colors flex items-center gap-2 shadow-sm"
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : 'Connect & Index'}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export function ZipUploadModal({ isOpen, onClose, onSubmit }: ModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError('');
    setLoading(true);
    try {
      await onSubmit(file);
      setFile(null);
      onClose();
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-md">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="bg-white border border-slate-200 rounded-2xl p-6 w-full max-w-md shadow-2xl relative"
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-900 transition-colors"
            >
              <X size={20} />
            </button>
            
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center text-indigo-600">
                <UploadCloud size={20} />
              </div>
              <h2 className="text-xl font-semibold text-slate-900">Upload Repository</h2>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                className="border-2 border-dashed border-slate-300 hover:border-indigo-400 bg-slate-50 hover:bg-indigo-50 rounded-xl p-8 text-center transition-all cursor-pointer"
                onClick={() => document.getElementById('zip-upload')?.click()}
              >
                <input
                  id="zip-upload"
                  type="file"
                  accept=".zip"
                  className="hidden"
                  onChange={(e) => e.target.files && setFile(e.target.files[0])}
                />
                <UploadCloud className="mx-auto text-indigo-400 mb-3" size={32} />
                <p className="text-slate-700 font-medium mb-1">
                  {file ? file.name : 'Click or drag ZIP file here'}
                </p>
                <p className="text-slate-500 text-sm">Supports up to 50MB</p>
              </div>

              {error && <p className="text-red-400 text-sm">{error}</p>}

              <button
                type="submit"
                disabled={loading || !file}
                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors flex justify-center items-center gap-2 shadow-sm"
              >
                {loading ? <Loader2 className="animate-spin" size={18} /> : 'Upload & Index'}
              </button>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
