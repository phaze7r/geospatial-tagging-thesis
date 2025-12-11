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
            // Fetch more commits to cover 6 months (approx)
            const resp = await fetch(`https://api.github.com/repos/${repo}/commits?per_page=100`);
            const data = await resp.json();
            return Array.isArray(data) ? data : [];
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

const Sidebar = ({ activeTab, setActiveTab }) => {
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
                <div className="text-xs text-gray-400 text-center">
                    v1.2.0 • Read Only Mode
                </div>
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

const StatCard = ({ title, value, footer, icon, color = "orange" }) => {
    // Dynamic color classes map
    const colorClasses = {
        orange: 'bg-orange-50 text-orange-500',
        blue: 'bg-blue-50 text-blue-500',
        green: 'bg-green-50 text-green-500',
        purple: 'bg-purple-50 text-purple-500'
    };

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover-lift">
            <div className="flex justify-between items-start mb-4">
                <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
                    <h3 className="text-3xl font-bold text-gray-800">{value}</h3>
                </div>
                <div className={`p-3 rounded-lg ${colorClasses[color] || colorClasses.orange}`}>
                    <i className={`fas ${icon} text-xl`}></i>
                </div>
            </div>
            {footer && <div className="text-sm text-gray-600 border-t pt-3 mt-2">{footer}</div>}
        </div>
    );
};

const ActivityChart = ({ commits }) => {
    // Generate last 6 months of dates
    const weeks = useMemo(() => {
        const today = new Date();
        const sixMonthsAgo = new Date();
        sixMonthsAgo.setMonth(today.getMonth() - 6);

        // Align to previous Sunday
        sixMonthsAgo.setDate(sixMonthsAgo.getDate() - sixMonthsAgo.getDay());

        const dates = [];
        let currentDate = new Date(sixMonthsAgo);

        while (currentDate <= today) {
            dates.push(new Date(currentDate));
            currentDate.setDate(currentDate.getDate() + 1);
        }
        return dates;
    }, []);

    const activityMap = useMemo(() => {
        const map = {};
        commits.forEach(c => {
            const dateStr = c.commit.author.date.split('T')[0];
            map[dateStr] = (map[dateStr] || 0) + 1;
        });
        return map;
    }, [commits]);

    const getIntensity = (count) => {
        if (!count) return 'bg-gray-100';
        if (count == 1) return 'bg-orange-200';
        if (count <= 3) return 'bg-orange-300';
        return 'bg-orange-500';
    };

    return (
        <div className="bg-white p-4 md:p-6 rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <h3 className="font-bold text-gray-800 mb-4 md:mb-6 flex items-center gap-2">
                <i className="fab fa-github text-gray-700"></i>
                Contribution Activity (6 Months)
            </h3>

            <div className="overflow-x-auto pb-2 scrollbar-hide">
                <div className="flex gap-1 justify-start min-w-max">
                    {weeks.map((date, i) => {
                        const dateStr = date.toISOString().split('T')[0];
                        const count = activityMap[dateStr] || 0;
                        return (
                            <div
                                key={dateStr}
                                className={`w-3 h-3 rounded-sm ${getIntensity(count)} tooltip cursor-default`}
                                data-tooltip={`${count} commits on ${dateStr}`}
                            ></div>
                        );
                    })}
                </div>
            </div>
            <div className="flex items-center gap-2 mt-4 text-xs text-gray-400">
                <span>Less</span>
                <div className="w-3 h-3 rounded-sm bg-gray-100"></div>
                <div className="w-3 h-3 rounded-sm bg-orange-200"></div>
                <div className="w-3 h-3 rounded-sm bg-orange-300"></div>
                <div className="w-3 h-3 rounded-sm bg-orange-500"></div>
                <span>More</span>
            </div>
        </div>
    );
};

const NotesFeed = ({ notes }) => {
    return (
        <div className="bg-white p-4 md:p-6 rounded-xl shadow-sm border border-gray-100 h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold text-gray-800">
                    <i className="fas fa-sticky-note text-orange-500 mr-2"></i>
                    Updates & Notes
                </h3>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar max-h-[400px]">
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

const Dashboard = ({ config, commits }) => {
    return (
        <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6">
            <header>
                <h2 className="text-xl md:text-2xl font-bold text-gray-800">Overview</h2>
                <p className="text-sm md:text-base text-gray-500">Project status and recent activity.</p>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
                <StatCard
                    title="Thesis Progress"
                    value={`${config.progress || 0}%`}
                    icon="fa-tasks"
                    footer={
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                            <div className="bg-orange-500 h-2 rounded-full" style={{ width: `${config.progress}%` }}></div>
                        </div>
                    }
                />
                <StatCard
                    title="Recent Commits"
                    value={commits.length}
                    icon="fa-code-branch"
                    color="blue"
                    footer="In loaded history"
                />
                <StatCard
                    title="Total Reports"
                    value={Object.keys(config.reports || {}).length}
                    icon="fa-file-alt"
                    color="green"
                    footer="Available in Docs"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <ActivityChart commits={commits} />
                </div>
                <div>
                    <NotesFeed notes={config.notes || []} />
                </div>
            </div>
        </div>
    );
};

const ReportsViewer = () => {
    const [selectedReport, setSelectedReport] = useState(null);
    const [content, setContent] = useState('');

    // Derived state for mobile view logic
    const isMobileView = window.innerWidth < 768; // Simple check, or just use CSS classes

    // Hardcoded list for now
    const reports = [
        { id: 'features', title: 'Feature Splits Analysis', date: '2025-08-15', path: 'reports/features_splits_20250815.md' },
        { id: 'patterns', title: 'Pattern Mining Results', date: '2025-08-15', path: 'reports/patterns_mining_20250815.md' },
        { id: 'accuracy', title: 'Accuracy Analysis', date: '2025-12-10', path: 'reports/accuracy_analysis.md' },
        { id: 'xai', title: 'XAI Summary', date: '2025-12-10', path: 'reports/xai_summary.md' },
        { id: 'data', title: 'Extended Labels Data', date: '2025-12-10', path: 'reports/extended_labels_data.md' }
    ];

    useEffect(() => {
        if (selectedReport) {
            DataService.loadMarkdown(selectedReport.path).then(text => {
                setContent(text);
            });
        }
    }, [selectedReport]);

    return (
        <div className="p-4 md:p-8 max-w-7xl mx-auto h-[calc(100vh-4rem)] md:h-[calc(100vh-2rem)] flex gap-6 relative">
            {/* List Column - Hidden on mobile if report selected */}
            <div className={`w-full md:w-1/3 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col absolute md:relative inset-0 z-10 md:z-auto ${selectedReport ? 'hidden md:flex' : 'flex'}`}>
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

            {/* Content Column - Full screen on mobile when selected */}
            <div className={`w-full md:flex-1 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col absolute md:relative inset-0 z-20 md:z-auto bg-white ${selectedReport ? 'flex' : 'hidden md:flex'}`}>
                {selectedReport ? (
                    <>
                        <div className="md:hidden p-3 border-b flex items-center gap-2 bg-gray-50">
                            <button onClick={() => setSelectedReport(null)} className="text-gray-600 hover:text-orange-500 font-medium">
                                <i className="fas fa-arrow-left mr-1"></i> Back
                            </button>
                            <span className="text-sm font-medium text-gray-400">|</span>
                            <span className="text-sm font-semibold truncate text-gray-800">{selectedReport.title}</span>
                        </div>
                        <div className="flex-1 overflow-y-auto p-4 md:p-8 custom-scrollbar">
                            <div className="markdown-body" dangerouslySetInnerHTML={{ __html: marked.parse(content) }}></div>
                        </div>
                    </>
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
        <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 h-[calc(100vh-4rem)] md:h-auto overflow-hidden md:overflow-visible">
            <h2 className="text-2xl font-bold text-gray-800">Data Explorer</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-full md:h-[600px]">
                {/* File Tree - Hidden on mobile if file selected */}
                <div className={`bg-white rounded-xl shadow-sm border border-gray-100 p-4 h-full md:h-full overflow-y-auto ${selectedFile ? 'hidden md:block' : 'block'}`}>
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

                {/* Content Preview - Full screen mobile if selected */}
                <div className={`md:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-4 md:p-6 h-full md:h-full overflow-hidden flex flex-col ${selectedFile ? 'block' : 'hidden md:flex'}`}>
                    {selectedFile ? (
                        <>
                            <div className="flex justify-between items-center mb-4">
                                <div className="flex items-center gap-2 overflow-hidden">
                                    <button onClick={() => setSelectedFile(null)} className="md:hidden text-gray-600 mr-2">
                                        <i className="fas fa-arrow-left"></i>
                                    </button>
                                    <h3 className="font-semibold text-gray-800 truncate">{selectedFile.path}</h3>
                                </div>
                                <span className="text-xs bg-gray-100 px-2 py-1 rounded whitespace-nowrap">Top 20</span>
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

// --- Main App ---

const App = () => {
    const [config, setConfig] = useState(null);
    const [commits, setCommits] = useState([]);
    const [activeTab, setActiveTab] = useState('dashboard');
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
            case 'dashboard': return <Dashboard config={config} commits={commits} />;
            case 'reports': return <ReportsViewer />;
            case 'data': return <DataExplorer config={config.config} />;
            default: return <Dashboard config={config} />;
        }
    };

    return (
        <div className="flex min-h-screen bg-gray-50/50">
            <Sidebar
                activeTab={activeTab}
                setActiveTab={(tab) => { setActiveTab(tab); setMobileMenuOpen(false); }}
            />

            <div className="flex-1 flex flex-col min-w-0">
                <MobileHeader onMenuClick={() => setMobileMenuOpen(!mobileMenuOpen)} />

                {/* Mobile Menu Overlay */}
                {mobileMenuOpen && (
                    <div className="md:hidden fixed inset-0 z-40 bg-gray-800 bg-opacity-75" onClick={() => setMobileMenuOpen(false)}>
                        <div className="w-64 bg-white h-full shadow-xl" onClick={e => e.stopPropagation()}>
                            <div className="p-4 font-bold border-b">Menu</div>
                            <nav className="p-4 space-y-2">
                                <button onClick={() => { setActiveTab('dashboard'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Dashboard</button>
                                <button onClick={() => { setActiveTab('reports'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Reports</button>
                                <button onClick={() => { setActiveTab('data'); setMobileMenuOpen(false) }} className="block w-full text-left p-2 hover:bg-gray-100 rounded">Data</button>
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
