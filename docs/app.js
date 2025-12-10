const { useState, useEffect, useMemo } = React;

// --- API Service ---
const DataService = {
    async loadConfig() {
        // Try fetch first (for HTTP server), fallback to window.LOCAL_DATA (for file://)
        try {
            const resp = await fetch('data.json');
            if (!resp.ok) throw new Error('Failed to load local data');
            return await resp.json();
        } catch (e) {
            console.log("Fetch failed, using local fallback");
            return window.LOCAL_DATA || null;
        }
    },

    async loadMarkdown(path) {
        // Try to get from local bundled data first
        if (window.LOCAL_DATA && window.LOCAL_DATA.reports && window.LOCAL_DATA.reports[path]) {
            return window.LOCAL_DATA.reports[path];
        }

        try {
            const resp = await fetch(path);
            if (!resp.ok) throw new Error('Failed to load markdown');
            return await resp.text();
        } catch (e) {
            return '# Error loading report\n\nCould not load report file. If you are viewing this locally without a web server, browser security blocks loading external files. Please use a local server or update `docs/data.js`.';
        }
    },

    // GitHub API Helper
    async fetchCommits(repo) {
        try {
            const resp = await fetch(`https://api.github.com/repos/${repo}/commits?per_page=50`);
            return await resp.json();
        } catch (e) {
            console.warn('GitHub API failed', e);
            return [];
        }
    },

    async fetchRepoTree(repo) {
        try {
            const response = await fetch(`https://api.github.com/repos/${repo}/git/trees/main?recursive=1`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching repo tree:', error);
            return { tree: [] };
        }
    },

    async fetchFileContent(repo, path) {
        try {
            const response = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`);
            const data = await response.json();
            return atob(data.content); // Basic Base64 decode
        } catch (error) {
            console.error('Error fetching file content:', error);
            return '';
        }
    }
};

// --- Components ---

const Sidebar = ({ activeTab, setActiveTab, user, onLogout }) => {
    const menuItems = [
        { id: 'dashboard', icon: 'fa-chart-line', label: 'Dashboard' },
        { id: 'reports', icon: 'fa-file-alt', label: 'Reports' },
        { id: 'data', icon: 'fa-database', label: 'Data & Source' },
    ];

    return (
        <aside className="w-64 bg-white hidden md:flex flex-col border-r border-gray-200 h-screen sticky top-0">
            <div className="p-6 flex items-center gap-3 border-b border-gray-100">
                <div className="text-3xl animate-bounce-gentle">🤖</div>
                <div>
                    <h1 className="font-bold text-gray-800 text-lg leading-tight">Geospatial<br />Thesis</h1>
                </div>
            </div>

            <nav className="flex-1 p-4 space-y-2">
                {menuItems.map(item => (
                    <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left rounded-lg transition-colors ${activeTab === item.id
                            ? 'bg-orange-50 text-orange-600 font-semibold'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                            }`}
                    >
                        <i className={`fas ${item.icon} w-5 text-center`}></i>
                        {item.label}
                    </button>
                ))}
            </nav>

            <div className="p-4 border-t border-gray-100">
                {user ? (
                    <div className="bg-gray-50 p-3 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 font-bold">
                                {user.username[0].toUpperCase()}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">{user.username}</p>
                                <p className="text-xs text-gray-500 capitalize">{user.role}</p>
                            </div>
                        </div>
                        <button
                            onClick={onLogout}
                            className="w-full text-xs text-red-600 hover:text-red-700 font-medium py-1"
                        >
                            Sign Out
                        </button>
                    </div>
                ) : (
                    <button
                        onClick={() => setActiveTab('login')}
                        className="w-full bg-gray-900 text-white py-2 rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
                    >
                        Admin Login
                    </button>
                )}
            </div>
        </aside>
    );
};

const MobileHeader = ({ onMenuClick }) => (
    <header className="md:hidden bg-white border-b p-4 flex justify-between items-center sticky top-0 z-20">
        <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <span className="font-bold text-gray-800">Geospatial Thesis</span>
        </div>
        <button onClick={onMenuClick} className="text-gray-600 p-2">
            <i className="fas fa-bars text-xl"></i>
        </button>
    </header>
);

const StatCard = ({ title, value, footer, icon, color = "orange" }) => (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover-lift">
        <div className="flex justify-between items-start mb-4">
            <div>
                <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
                <h3 className="text-3xl font-bold text-gray-800">{value}</h3>
            </div>
            <div className={`p-3 rounded-lg bg-${color}-50 text-${color}-500`}>
                <i className={`fas ${icon} text-xl`}></i>
            </div>
        </div>
        {footer && <div className="text-sm text-gray-600 border-t pt-3 mt-2">{footer}</div>}
    </div>
);

const ActivityChart = ({ commits }) => {
    // Basic heatmap visualization
    const days = useMemo(() => {
        const d = [];
        for (let i = 29; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            d.push(date.toISOString().split('T')[0]);
        }
        return d;
    }, []);

    const activity = useMemo(() => {
        const counts = {};
        commits.forEach(c => {
            const date = c.commit.author.date.split('T')[0];
            counts[date] = (counts[date] || 0) + 1;
        });
        return counts;
    }, [commits]);

    const getColor = (count) => {
        if (!count) return 'bg-gray-100';
        if (count < 2) return 'bg-orange-200';
        if (count < 4) return 'bg-orange-300';
        return 'bg-orange-500';
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <h3 className="font-bold text-gray-800 mb-4 flex items-center gap-2">
                <i className="fas fa-chart-bar text-orange-500"></i>
                Contribution Activity (30 Days)
            </h3>
            <div className="flex gap-1 justify-between items-end h-24">
                {days.map(day => {
                    const count = activity[day] || 0;
                    const height = Math.max(10, Math.min(100, count * 20)); // Scale height
                    return (
                        <div key={day} className="flex-1 flex flex-col items-center gap-1 group relative">
                            <div
                                className={`w-full rounded-t-sm transition-all ${getColor(count)}`}
                                style={{ height: `${height}%` }}
                            ></div>
                            <div className="absolute bottom-full mb-2 hidden group-hover:block bg-gray-800 text-white text-xs p-2 rounded whitespace-nowrap z-10">
                                {count} commits on {day}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

const NotesFeed = ({ notes, user, onAddNote }) => {
    const [isAdding, setIsAdding] = useState(false);
    const [newNote, setNewNote] = useState("");

    const handleSave = () => {
        if (!newNote.trim()) return;
        onAddNote({
            content: newNote,
            date: new Date().toISOString().split('T')[0],
            author: user.username
        });
        setNewNote("");
        setIsAdding(false);
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold text-gray-800">
                    <i className="fas fa-sticky-note text-orange-500 mr-2"></i>
                    Updates & Notes
                </h3>
                {user && (
                    <button
                        onClick={() => setIsAdding(!isAdding)}
                        className="text-sm bg-orange-50 text-orange-600 px-3 py-1 rounded hover:bg-orange-100"
                    >
                        {isAdding ? 'Cancel' : '+ Add Note'}
                    </button>
                )}
            </div>

            {isAdding && (
                <div className="mb-4 animate-slide-up">
                    <textarea
                        className="w-full p-3 border rounded-lg text-sm focus:ring-2 focus:ring-orange-500 outline-none"
                        rows="3"
                        placeholder="What's new?"
                        value={newNote}
                        onChange={e => setNewNote(e.target.value)}
                    ></textarea>
                    <button onClick={handleSave} className="mt-2 bg-orange-500 text-white px-4 py-1.5 rounded-lg text-sm">Post Update</button>
                </div>
            )}

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar">
                {notes.map((note, i) => (
                    <div key={i} className="flex gap-3 animate-slide-up" style={{ animationDelay: `${i * 0.05}s` }}>
                        <div className="w-10 h-10 rounded-full bg-gray-100 flex-shrink-0 flex items-center justify-center text-gray-500">
                            <i className="fas fa-user-circle text-xl"></i>
                        </div>
                        <div>
                            <div className="bg-gray-50 p-3 rounded-lg rounded-tl-none">
                                <p className="text-gray-800 text-sm">{note.content}</p>
                            </div>
                            <div className="text-xs text-gray-400 mt-1 ml-1">
                                {note.date} • {note.author}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

const Dashboard = ({ config, setConfig, commits, user }) => {
    // Handle updates to local state to "simulate" DB updates
    const handleUpdateProgress = (val) => {
        setConfig(prev => ({ ...prev, progress: parseInt(val) }));
    };

    const handleAddNote = (note) => {
        const newNote = { ...note, id: Date.now() };
        setConfig(prev => ({
            ...prev,
            notes: [newNote, ...(prev.notes || [])]
        }));
    };

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            <header className="flex justify-between items-end">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">Overview</h2>
                    <p className="text-gray-500">Welcome to the project dashboard.</p>
                </div>
                {user && (
                    <button
                        onClick={() => {
                            // Create a Blob and download
                            const dataStr = JSON.stringify(config, null, 2);
                            const blob = new Blob([dataStr], { type: "application/json" });
                            const url = URL.createObjectURL(blob);
                            const link = document.createElement("a");
                            link.href = url;
                            link.download = "data.json";
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                            alert("Downloaded data.json! Please commit this file to your repository to persist changes.");
                        }}
                        className="bg-gray-900 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-gray-800"
                    >
                        <i className="fas fa-download"></i> Save Changes
                    </button>
                )}
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Thesis Progress"
                    value={`${config.progress || 0}%`}
                    icon="fa-tasks"
                    footer={
                        user ? (
                            <input
                                type="range"
                                className="w-full mt-2 accent-orange-500"
                                value={config.progress || 0}
                                onChange={(e) => handleUpdateProgress(e.target.value)}
                            />
                        ) : (
                            <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                                <div className="bg-orange-500 h-2 rounded-full" style={{ width: `${config.progress}%` }}></div>
                            </div>
                        )
                    }
                />
                <StatCard
                    title="Recent Commits"
                    value={commits.length}
                    icon="fa-code-branch"
                    color="blue"
                    footer="In the last 30 days"
                />
                <StatCard
                    title="Total Reports"
                    value="2"
                    icon="fa-file-alt"
                    color="green"
                    footer="Available in Docs"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 min-h-[400px]">
                <ActivityChart commits={commits} />
                <NotesFeed
                    notes={config.notes || []}
                    user={user}
                    onAddNote={handleAddNote}
                />
            </div>
        </div>
    );
};

const ReportsViewer = () => {
    const [selectedReport, setSelectedReport] = useState(null);
    const [content, setContent] = useState('');

    // Hardcoded list for now, or we could fetch file list if we had an API
    const reports = [
        { id: 'features', title: 'Feature Splits Analysis', date: '2025-08-15', path: 'reports/features_splits_20250815.md' },
        { id: 'patterns', title: 'Pattern Mining Results', date: '2025-08-15', path: 'reports/patterns_mining_20250815.md' }
    ];

    useEffect(() => {
        if (selectedReport) {
            DataService.loadMarkdown(selectedReport.path).then(text => {
                setContent(text);
            });
        }
    }, [selectedReport]);

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto h-[calc(100vh-2rem)] flex gap-6">
            <div className="w-1/3 bg-white  rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                <div className="p-4 border-b bg-gray-50">
                    <h3 className="font-bold text-gray-700">Available Reports</h3>
                </div>
                <div className="overflow-y-auto flex-1 p-2 space-y-2">
                    {reports.map(r => (
                        <div
                            key={r.id}
                            onClick={() => setSelectedReport(r)}
                            className={`p-3 rounded-lg cursor-pointer transition-colors ${selectedReport?.id === r.id ? 'bg-orange-50 border-orange-200 border' : 'hover:bg-gray-50 border border-transparent'}`}
                        >
                            <h4 className="font-medium text-gray-800">{r.title}</h4>
                            <p className="text-xs text-gray-500">{r.date}</p>
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                {selectedReport ? (
                    <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
                        <div className="markdown-body" dangerouslySetInnerHTML={{ __html: marked.parse(content) }}></div>
                    </div>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-400 flex-col">
                        <i className="fas fa-file-alt text-4xl mb-3 opacity-50"></i>
                        <p>Select a report to view details</p>
                    </div>
                )}
            </div>
        </div>
    );
};

const DataExplorer = ({ config }) => {
    const [tree, setTree] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const [fileContent, setFileContent] = useState('');

    useEffect(() => {
        if (config.githubRepo) {
            setLoading(true);
            DataService.fetchRepoTree(config.githubRepo).then(data => {
                setTree(data.tree || []);
                setLoading(false);
            });
        }
    }, [config]);

    const handleFileClick = async (file) => {
        if (file.path.endsWith('.csv')) {
            setSelectedFile(file);
            const content = await DataService.fetchFileContent(config.githubRepo, file.path);
            setFileContent(content);
        } else {
            window.open(`https://github.com/${config.githubRepo}/blob/main/${file.path}`, '_blank');
        }
    };

    const csvData = useMemo(() => {
        if (!fileContent) return [];
        const lines = fileContent.split('\n').filter(l => l.trim());
        if (lines.length === 0) return [];
        const headers = lines[0].split(',');
        const rows = lines.slice(1, 20).map(l => l.split(','));
        return { headers, rows };
    }, [fileContent]);

    return (
        <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
            <h2 className="text-2xl font-bold text-gray-800">Data Explorer</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 h-[600px] overflow-y-auto">
                    <h3 className="font-semibold text-gray-700 mb-4 px-2">Repository Files</h3>
                    {loading ? <div className="text-center p-4">Loading...</div> : (
                        <div className="space-y-1">
                            {tree.filter(i => i.path.startsWith('data/') || i.path.endsWith('.csv')).map(item => (
                                <div
                                    key={item.path}
                                    onClick={() => handleFileClick(item)}
                                    className={`flex items-center gap-2 p-2 rounded cursor-pointer text-sm ${selectedFile?.path === item.path ? 'bg-orange-50 text-orange-700' : 'hover:bg-gray-50 text-gray-600'}`}
                                >
                                    <i className={`fas ${item.path.endsWith('.csv') ? 'fa-table' : 'fa-folder'} ${item.path.endsWith('.csv') ? 'text-green-500' : 'text-blue-300'}`}></i>
                                    <span className="truncate">{item.path}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6 h-[600px] overflow-hidden flex flex-col">
                    {selectedFile ? (
                        <>
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="font-semibold text-gray-800">{selectedFile.path}</h3>
                                <span className="text-xs bg-gray-100 px-2 py-1 rounded">Preview (Top 20 rows)</span>
                            </div>
                            <div className="flex-1 overflow-auto border rounded-lg">
                                <table className="min-w-full text-sm text-left">
                                    <thead className="bg-gray-50 sticky top-0">
                                        <tr>
                                            {csvData.headers?.map((h, i) => (
                                                <th key={i} className="px-4 py-2 font-medium text-gray-600 border-b">{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {csvData.rows?.map((row, i) => (
                                            <tr key={i} className="hover:bg-gray-50">
                                                {row.map((cell, j) => (
                                                    <td key={j} className="px-4 py-2 border-b text-gray-600">{cell}</td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-gray-400">
                            <p>Select a CSV file to preview data</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const LoginView = ({ onLogin }) => {
    const [user, setUser] = useState('');
    const [pass, setPass] = useState('');
    const [err, setErr] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        // Simple mock auth
        if (user === 'admin' && pass === 'admin123') {
            onLogin({ username: 'admin', role: 'admin' });
        } else if (user === 'user' && pass === 'user') {
            onLogin({ username: 'user', role: 'viewer' });
        } else {
            setErr('Invalid credentials (try admin/admin123)');
        }
    };

    return (
        <div className="flex items-center justify-center h-full min-h-[500px]">
            <div className="bg-white p-8 rounded-xl shadow-lg max-w-sm w-full border border-gray-100">
                <h2 className="text-2xl font-bold text-center mb-6">Access Dashboard</h2>
                {err && <div className="bg-red-50 text-red-600 p-3 rounded mb-4 text-sm">{err}</div>}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                        <input
                            type="text"
                            className="w-full p-2 border rounded focus:light-orange-500"
                            value={user}
                            onChange={e => setUser(e.target.value)}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                        <input
                            type="password"
                            className="w-full p-2 border rounded"
                            value={pass}
                            onChange={e => setPass(e.target.value)}
                        />
                    </div>
                    <button className="w-full bg-orange-500 text-white py-2 rounded-lg hover:bg-orange-600">Login</button>
                    <div className="text-center text-xs text-gray-400 mt-4">
                        Demo: admin / admin123
                    </div>
                </form>
            </div>
        </div>
    );
};

// --- Main App ---

const App = () => {
    const [config, setConfig] = useState(null);
    const [commits, setCommits] = useState([]);
    const [activeTab, setActiveTab] = useState('dashboard');
    const [user, setUser] = useState(null);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    useEffect(() => {
        // Load initial data
        DataService.loadConfig().then(data => {
            if (data) {
                setConfig(data);
                // Then fetch commits
                if (data.config?.githubRepo) {
                    DataService.fetchCommits(data.config.githubRepo).then(setCommits);
                }
            }
        });
    }, []);

    if (!config) return <div className="flex items-center justify-center h-screen"><i className="fas fa-circle-notch fa-spin text-orange-500 text-2xl"></i></div>;

    const renderContent = () => {
        switch (activeTab) {
            case 'dashboard': return <Dashboard config={config} setConfig={setConfig} commits={commits} user={user} />;
            case 'reports': return <ReportsViewer />;
            case 'data': return <DataExplorer config={config.config} />;
            case 'login': return <LoginView onLogin={(u) => { setUser(u); setActiveTab('dashboard'); }} />;
            default: return <Dashboard config={config} />;
        }
    };

    return (
        <div className="flex min-h-screen bg-gray-50/50">
            <Sidebar
                activeTab={activeTab}
                setActiveTab={(tab) => { setActiveTab(tab); setMobileMenuOpen(false); }}
                user={user}
                onLogout={() => { setUser(null); setActiveTab('dashboard'); }}
            />

            <div className="flex-1 flex flex-col min-w-0">
                <MobileHeader onMenuClick={() => setMobileMenuOpen(!mobileMenuOpen)} />

                {/* Mobile Menu Overlay */}
                {mobileMenuOpen && (
                    <div className="md:hidden fixed inset-0 z-40 bg-gray-800 bg-opacity-75" onClick={() => setMobileMenuOpen(false)}>
                        <div className="w-64 bg-white h-full shadow-xl" onClick={e => e.stopPropagation()}>
                            {/* Reusing sidebar logic essentially, but simplified for brevity */}
                            <div className="p-4 font-bold border-b">Menu</div>
                            <nav className="p-4 space-y-2">
                                <button onClick={() => { setActiveTab('dashboard'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Dashboard</button>
                                <button onClick={() => { setActiveTab('reports'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Reports</button>
                                <button onClick={() => { setActiveTab('data'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Data</button>
                                {!user ? (
                                    <button onClick={() => { setActiveTab('login'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 bg-gray-900 text-white rounded mt-4">Login</button>
                                ) : (
                                    <button onClick={() => { setUser(null); setMobileMenuOpen(false) }} className="block w-full text-left p-2 text-red-500 rounded mt-4">Logout</button>
                                )}
                            </nav>
                        </div>
                    </div>
                )}

                <main className="flex-1 overflow-y-auto">
                    {renderContent()}
                </main>
            </div>
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />); 
