const { useState, useEffect, useMemo } = React;

// --- API Service ---
const DataService = {
    async loadConfig() {
        try {
            const resp = await fetch('/api/data');
            if (!resp.ok) throw new Error('Failed to load data');
            return await resp.json();
        } catch (e) {
            console.error("API Fetch failed", e);
            return null;
        }
    },

    async loadMarkdown(path) {
        try {
            const resp = await fetch(path);
            if (!resp.ok) throw new Error('Failed to load markdown');
            return await resp.text();
        } catch (e) {
            return '# Error loading report\n\nCould not load report file.';
        }
    },

    async getAccuracyData() {
        try {
            const resp = await fetch('/api/reports/accuracy');
            if (!resp.ok) throw new Error('Failed to load accuracy data');
            return await resp.json();
        } catch (e) {
            console.error("Accuracy fetch failed", e);
            return null;
        }
    },

    async fetchCommits(repo) {
        try {
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
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error fetching repo tree:', error);
            return { tree: [] };
        }
    },

    async fetchFileContent(repo, path) {
        try {
            const response = await fetch(`https://api.github.com/repos/${repo}/contents/${path}`);
            const data = await response.json();
            return atob(data.content);
        } catch (error) {
            console.error('Error fetching file content:', error);
            return '';
        }
    }
};

// --- Components ---

const Sidebar = ({ activeTab, setActiveTab, isCollapsed, setCollapsed, mobileOpen, closeMobileMenu }) => {
    const menuItems = [
        { id: 'dashboard', icon: 'fa-chart-line', label: 'Dashboard' },
        { id: 'reports', icon: 'fa-file-alt', label: 'Reports' },
        { id: 'data', icon: 'fa-database', label: 'Data & Source' },
    ];

    return (
        <aside 
            className={`glass fixed md:sticky top-0 z-50 h-screen transition-all duration-300 
            ${mobileOpen ? 'translate-x-0 w-64' : '-translate-x-full md:translate-x-0'} 
            ${isCollapsed ? 'md:w-20' : 'md:w-64'}
            md:flex flex-col border-r border-white/20 bg-white/80 backdrop-blur-xl`}
            onMouseEnter={() => window.innerWidth >= 768 && setCollapsed(false)}
            onMouseLeave={() => window.innerWidth >= 768 && setCollapsed(true)}
        >
            <div className="p-6 flex items-center justify-between border-b border-white/20 h-20">
                <div className="flex items-center gap-3">
                    <div className="text-3xl animate-bounce-gentle shrink-0">🤖</div>
                    <div className={`overflow-hidden transition-all duration-300 ${isCollapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
                        <h1 className="font-bold text-gray-800 text-lg leading-tight tracking-tight whitespace-nowrap">Geospatial<br />Thesis</h1>
                    </div>
                </div>
                {/* Mobile Close Button */}
                <button onClick={closeMobileMenu} className="md:hidden text-gray-500 hover:text-red-500 p-2">
                    <i className="fas fa-times text-xl"></i>
                </button>
            </div>

            <nav className="flex-1 p-4 space-y-2">
                {menuItems.map(item => (
                    <button
                        key={item.id}
                        onClick={() => setActiveTab(item.id)}
                        className={`w-full flex items-center gap-3 px-4 py-3 text-left rounded-xl transition-all duration-300 group relative ${activeTab === item.id
                            ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/30'
                            : 'text-gray-600 hover:bg-white/50 hover:text-gray-900'
                            }`}
                    >
                        <i className={`fas ${item.icon} w-5 text-center shrink-0`}></i>
                        <span className={`font-medium transition-all duration-300 ${isCollapsed ? 'hidden' : 'block'}`}>{item.label}</span>

                        {/* Tooltip for collapsed state */}
                        {isCollapsed && (
                            <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 whitespace-nowrap z-50 pointer-events-none">
                                {item.label}
                            </div>
                        )}
                    </button>
                ))}
            </nav>

            <div className={`p-4 border-t border-white/20 flex items-center gap-3 transition-all duration-300 ${isCollapsed ? 'justify-center mx-1' : ''}`}>
                <div className="w-10 h-10 rounded-full bg-gray-200 overflow-hidden shrink-0 border-2 border-white shadow-sm">
                    <img src="/static/img/faizan.jpg" alt="Faizan" className="w-full h-full object-cover" onError={(e) => e.target.src = 'https://ui-avatars.com/api/?name=Faizan&background=random'} />
                </div>
                <div className={`overflow-hidden transition-all duration-300 ${isCollapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'}`}>
                    <p className="text-sm font-bold text-gray-800">Faizan</p>
                    <p className="text-xs text-gray-500">Reseracher</p>
                </div>
            </div>
        </aside >
    );
};

const MobileHeader = ({ onMenuClick }) => (
    <header className="md:hidden glass border-b border-white/20 p-4 flex justify-between items-center sticky top-0 z-20">
        <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <div>
                <span className="font-bold text-gray-800 block text-xs">Geospatial Tagging Thesis</span>
            </div>
        </div>
        <button onClick={onMenuClick} className="text-gray-600 p-2">
            <i className="fas fa-bars text-xl"></i>
        </button>
    </header>
);

const Footer = () => (
    <footer className="mt-12 pt-8 border-t border-gray-200/50 pb-8 text-center text-sm text-gray-500">
        <div className="flex justify-center gap-6 mb-4">
            <a href="https://github.com/phaze7r" target="_blank" className="hover:text-blue-500 transition-colors"><i className="fab fa-github text-xl"></i></a>
            <a href="https://www.linkedin.com/in/faizan7r" target="_blank" className="hover:text-blue-500 transition-colors"><i className="fab fa-linkedin text-xl"></i></a>
        </div>
        <p className="mb-2">© 2025 Geospatial Tagging Thesis. All rights reserved.</p>
        <p className="text-xs text-gray-400">Released under MIT Open License.</p>
    </footer>
);

const FullWidthProgress = ({ title, value, color = "orange" }) => {
    return (
        <div className="glass p-6 rounded-2xl flex flex-col md:flex-row items-center gap-6 hover-lift border-l-4 border-orange-500">
            <div className="flex items-center gap-4 shrink-0">
                <div className={`w-12 h-12 rounded-full bg-orange-100 flex items-center justify-center text-orange-500`}>
                    <i className="fas fa-rocket text-xl"></i>
                </div>
                <div>
                    <h3 className="text-lg font-bold text-gray-800">{title}</h3>
                    <p className="text-sm text-gray-500 font-medium">{value}% Complete</p>
                </div>
            </div>

            <div className="flex-1 w-full">
                <div className="w-full bg-gray-200/50 rounded-full h-4 overflow-hidden relative shadow-inner">
                    <div
                        className="bg-gradient-to-r from-orange-400 via-orange-500 to-red-500 h-full rounded-full relative overflow-hidden"
                        style={{ width: `${value}%` }}
                    >
                        <div className="absolute inset-0 bg-white/20 w-full h-full animate-[shimmer_2s_infinite]"></div>
                    </div>
                </div>
            </div>

            <div className="shrink-0 text-right hidden md:block">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-widest">Status</span>
                <p className="text-sm font-semibold text-emerald-600">On Track</p>
            </div>
        </div>
    )
}

const StatCard = ({ title, value, footer, icon, color = "blue" }) => {
    const gradients = {
        orange: 'from-orange-500 to-red-500',
        blue: 'from-blue-500 to-cyan-500',
        green: 'from-emerald-500 to-teal-500',
        purple: 'from-violet-500 to-fuchsia-500'
    };

    return (
        <div className="glass p-6 rounded-2xl hover-lift relative overflow-hidden group">
            <div className={`absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity`}>
                <i className={`fas ${icon} text-6xl`}></i>
            </div>

            <div className="relative z-10">
                <p className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-1">{title}</p>
                <h3 className="text-3xl font-bold text-gray-800 mb-2">{value}</h3>
                <div className={`h-1 w-12 rounded-full bg-gradient-to-r ${gradients[color]}`}></div>
                {footer && <div className="mt-4 text-sm text-gray-500 font-medium">{footer}</div>}
            </div>
        </div>
    );
};

const AccuracyWidget = () => {
    const [data, setData] = useState(null);

    useEffect(() => {
        DataService.getAccuracyData().then(setData);
    }, []);

    if (!data) return null;

    return (
        <div className="glass p-6 rounded-2xl hover-lift border-t-4 border-emerald-500 relative group">
            <div className="flex justify-between items-center mb-6">
                <h3 className="font-bold text-gray-800 text-lg">
                    <i className="fas fa-bullseye text-emerald-500 mr-2"></i>
                    Model Accuracy
                </h3>
                <span className="text-xs font-mono text-gray-400">{new Date(data.timestamp).toLocaleDateString()}</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="relative group/item bg-white/50 p-4 rounded-xl text-center cursor-help transition-colors hover:bg-white/80">
                    <p className="text-xs text-gray-500 uppercase font-semibold border-b border-dashed border-gray-300 inline-block">Baseline</p>
                    <p className="text-2xl font-bold text-gray-700">{(data.baseline_word2vec_accuracy * 100).toFixed(2)}%</p>

                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-48 bg-gray-800 text-white text-xs p-2 rounded shadow-lg opacity-0 group-hover/item:opacity-100 transition-opacity pointer-events-none z-20">
                        Base Word2Vec implementation without extended features.
                        <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-800"></div>
                    </div>
                </div>

                <div className="relative group/item bg-gradient-to-br from-emerald-500 to-teal-600 p-4 rounded-xl text-center text-white shadow-lg shadow-emerald-500/20 cursor-help">
                    <p className="text-xs text-emerald-100 uppercase font-bold border-b border-dashed border-emerald-300 inline-block">Hybrid Model</p>
                    <p className="text-3xl font-bold">{(data.hybrid_model_accuracy * 100).toFixed(2)}%</p>
                    {/* Tooltip */}
                    <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-48 bg-gray-800 text-white text-xs p-2 rounded shadow-lg opacity-0 group-hover/item:opacity-100 transition-opacity pointer-events-none z-20">
                        Bayesian Elastic Net + Extended FP-Growth patterns.
                        <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-gray-800"></div>
                    </div>
                </div>
            </div>

            <div className="mt-4 flex justify-between items-center text-sm font-medium">
                <span className="text-gray-500">Net Improvement</span>
                <span className="text-emerald-600 bg-emerald-50 px-2 py-1 rounded-lg">
                    +{(data.improvement * 100).toFixed(2)}%
                </span>
            </div>
        </div>
    );
};

const ActivityChart = ({ commits, repo }) => {
    // Generate dates including past months
    const weeks = useMemo(() => {
        const today = new Date();
        const sixMonthsAgo = new Date();
        sixMonthsAgo.setMonth(today.getMonth() - 6);
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

    // Calculate month labels positions
    const monthLabels = useMemo(() => {
        const labels = [];
        let currentMonth = -1;
        // The grid is rendered column-by-column (weeks). 
        // 7 days per column.
        weeks.forEach((date, i) => {
            // Only check 1st day of each week (sunday) to decide if we place a label
            if (i % 7 === 0) {
                const m = date.getMonth();
                if (m !== currentMonth) {
                    labels.push({
                        text: date.toLocaleDateString('en-US', { month: 'short' }),
                        colIndex: Math.floor(i / 7)
                    });
                    currentMonth = m;
                }
            }
        });
        return labels;
    }, [weeks]);

    const getIntensity = (count) => {
        if (!count) return 'bg-gray-200/50';
        if (count == 1) return 'bg-blue-300';
        if (count <= 3) return 'bg-blue-400';
        return 'bg-blue-600';
    };

    return (
        <div className="glass p-8 rounded-3xl overflow-hidden w-full border border-white/40 shadow-xl">
            <h3 className="text-xl font-bold text-gray-800 mb-8 flex items-center gap-3">
                <i className="fab fa-github text-3xl text-gray-800"></i>
                <span className="flex-1">Repository Activity</span>
                <span className="text-sm font-normal text-gray-500 bg-white/50 px-3 py-1 rounded-full">
                    {commits.length} commits in last 6 months
                </span>
            </h3>

            <div className="overflow-x-auto pb-6 custom-scrollbar">
                <div className="relative min-w-max mx-auto">
                    {/* Month Labels */}
                    <div className="flex text-xs font-bold text-gray-400 mb-3 h-4 relative w-full">
                        {monthLabels.map((l, i) => (
                            <span key={i} style={{ left: `${l.colIndex * 22}px` }} className="absolute uppercase tracking-wider">
                                {l.text}
                            </span>
                        ))}
                    </div>

                    {/* Heatmap Grid: 7 rows (days), X cols (weeks) */}
                    {/* Pitch: w-4 (16px) + gap-1.5 (6px) = 22px */}
                    <div className="flex gap-x-[6px] gap-y-[6px] h-[160px] flex-wrap flex-col content-start">
                        {weeks.map((date, i) => {
                            const dateStr = date.toISOString().split('T')[0];
                            const count = activityMap[dateStr] || 0;
                            return (
                                <a
                                    key={dateStr}
                                    href={repo ? `https://github.com/${repo}/commits?until=${dateStr}` : '#'}
                                    target="_blank"
                                    className={`w-4 h-4 rounded-sm ${getIntensity(count)} transition-all duration-200 hover:scale-125 hover:ring-2 hover:ring-blue-500 hover:z-20 relative tooltip`}
                                    title={`${count} commits on ${dateStr}`}
                                ></a>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

// ... NotesFeed, ReportsViewer, DataExplorer ...
const NotesFeed = ({ notes }) => {
    return (
        <div className="glass p-6 rounded-xl h-full flex flex-col min-h-[250px]">
            <h3 className="font-bold text-gray-800 mb-4 flex items-center">
                <i className="fas fa-sticky-note text-amber-500 mr-2"></i>
                Updates & Notes
            </h3>

            <div className="flex-1 overflow-y-auto space-y-4 pr-2 custom-scrollbar max-h-[500px]">
                {notes.map((note, i) => (
                    <div key={i} className="flex gap-4 animate-slide-up bg-white/40 p-4 rounded-xl border border-white/50" style={{ animationDelay: `${i * 0.1}s` }}>
                        <div className="shrink-0">
                            {note.author.toLowerCase() === 'faizan' ? (
                                <img src="/static/img/faizan.jpg" alt="Faizan" className="w-10 h-10 rounded-full object-cover border-2 border-white shadow-sm" />
                            ) : (
                                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-100 to-orange-100 flex items-center justify-center text-amber-600 shadow-sm">
                                    <i className="fas fa-user-edit text-sm"></i>
                                </div>
                            )}
                        </div>
                        <div className="flex-1">
                            <div className="flex justify-between items-start mb-1">
                                <span className="text-xs font-bold text-gray-500 uppercase">{note.author}</span>
                                <span className="text-xs text-gray-400">{note.date}</span>
                            </div>
                            <p className="text-gray-800 text-sm leading-relaxed">{note.content}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
};

const Dashboard = ({ config, commits }) => {
    return (
        <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-6 animate-fade-in pb-20">
            <header className="mb-10 text-center md:text-left border-b border-gray-200/50 pb-6">
                <h1 className="text-4xl md:text-5xl font-extrabold text-gray-900 tracking-tight mb-4 leading-tight">
                    Geospatial Tagging of Volunteered Place Descriptions
                </h1>
                <p className="text-xl text-gray-600 font-light">
                    Bayesian Elastic Net & Extended FP-Growth Approach
                </p>
                <div className="mt-6 flex gap-6 text-sm text-gray-500 font-medium justify-center md:justify-start">
                    <span className="flex items-center gap-2 bg-white px-3 py-1 rounded-full shadow-sm border border-gray-100"><i className="fas fa-university text-blue-500"></i> MS Thesis</span>
                    <span className="flex items-center gap-2 bg-white px-3 py-1 rounded-full shadow-sm border border-gray-100"><i className="fas fa-calendar-alt text-orange-500"></i> 2024-2025</span>
                </div>
            </header>

            {/* Row 1: Full Width Progress */}
            <FullWidthProgress
                title="Thesis Completion"
                value={config.progress || 0}
            />

            {/* Row 2: Stat Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Commits"
                    value={commits.length}
                    icon="fa-code-branch"
                    color="blue"
                    footer="Last 6 months"
                />
                <StatCard
                    title="Reports"
                    value={(config.config?.reports?.length || 0) + 5}
                    icon="fa-file-wave"
                    color="purple"
                    footer="Generated Artifacts"
                />
                <StatCard
                    title="Data Files"
                    value="28"
                    icon="fa-database"
                    color="green"
                    footer="Processed Datasets"
                />
            </div>

            {/* Row 3: Detail Widgets */}
            {/* Row 3: Detail Widgets */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                    <AccuracyWidget />
                </div>
                <div>
                    <NotesFeed notes={config.notes || []} />
                </div>
            </div>

            {/* Row 4: GitHub Activity (Full Width) */}
            <div className="block -mt-4">
                <ActivityChart commits={commits} repo={config.config?.githubRepo} />
            </div>
        </div>
    );
};

const ReportsViewer = () => {
    const [selectedReport, setSelectedReport] = useState(null);
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(false);
    const [reports, setReports] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');

    useEffect(() => {
        DataService.loadConfig().then(data => {
            if (data?.config?.reports) {
                setReports(data.config.reports);
            }
        });
    }, []);

    useEffect(() => {
        if (selectedReport) {
            const ext = selectedReport.path.split('.').pop().toLowerCase();
            if (['md', 'txt'].includes(ext)) {
                setLoading(true);
                DataService.loadMarkdown(selectedReport.path).then(text => {
                    setContent(text);
                    setLoading(false);
                });
            } else {
                setContent('');
            }
        }
    }, [selectedReport]);

    const filteredReports = useMemo(() => {
        return reports.filter(r => r.title.toLowerCase().includes(searchTerm.toLowerCase()));
    }, [reports, searchTerm]);

    const renderToolbar = () => (
        <div className="h-16 border-b border-gray-200/50 bg-white/50 backdrop-blur flex justify-between items-center px-6 shrink-0">
            <div className="min-w-0">
                <h2 className="font-bold text-gray-800 truncate">{selectedReport.title}</h2>
                <p className="text-xs text-gray-500 font-mono">{selectedReport.date} • {selectedReport.path.split('.').pop().toUpperCase()}</p>
            </div>
            <div className="flex gap-2">
                <a 
                    href={selectedReport.path} 
                    download 
                    className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    title="Download"
                >
                    <i className="fas fa-download"></i>
                </a>
                <a 
                    href={selectedReport.path} 
                    target="_blank" 
                    className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="Open in New Tab"
                >
                    <i className="fas fa-external-link-alt"></i>
                </a>
            </div>
        </div>
    );

    const renderContent = () => {
        if (!selectedReport) return (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400 bg-gray-50/30">
                <div className="w-24 h-24 bg-white rounded-full shadow-sm flex items-center justify-center mb-6 animate-bounce-gentle">
                    <i className="fas fa-layer-group text-4xl text-purple-200"></i>
                </div>
                <h3 className="text-lg font-bold text-gray-600">Select an Artifact</h3>
                <p className="text-sm text-gray-400">View reports, images, and documents</p>
            </div>
        );
        
        const ext = selectedReport.path.split('.').pop().toLowerCase();

        if (loading) return <div className="flex-1 flex items-center justify-center text-gray-400"><i className="fas fa-circle-notch fa-spin text-2xl text-purple-500"></i></div>;

        if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
            return (
                <div className="flex-1 flex flex-col h-full bg-gray-100 relative overflow-hidden group">
                    {/* Checkerboard pattern for transparency */}
                    <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>
                    
                    <div className="flex-1 flex items-center justify-center p-8 overflow-auto z-10">
                         <img 
                            src={selectedReport.path} 
                            alt={selectedReport.title} 
                            className="max-w-full max-h-full object-contain rounded-lg shadow-2xl transition-transform duration-300 group-hover:scale-[1.01]" 
                        />
                    </div>
                </div>
            );
        }

        if (ext === 'pdf') {
            return (
                <div className="flex-1 w-full h-full bg-gray-50 p-4">
                    <iframe src={selectedReport.path} className="w-full h-full rounded-xl border border-gray-200 shadow-sm" title={selectedReport.title}></iframe>
                </div>
            );
        }

        if (['md', 'txt'].includes(ext)) {
             return (
                 <div className="flex-1 overflow-y-auto p-8 md:p-12 custom-scrollbar bg-white">
                     <div className="max-w-3xl mx-auto markdown-body bg-transparent" dangerouslySetInnerHTML={{ __html: marked.parse(content) }}></div>
                 </div>
             );
        }

        // Fallback
        return (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-500">
                <i className="fas fa-file-download text-5xl mb-4 text-gray-300"></i>
                <p className="mb-4">Preview not available for this file type.</p>
                <a href={selectedReport.path} target="_blank" className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 shadow-md hover:shadow-lg transition-all transform hover:-translate-y-0.5">
                    Download File
                </a>
            </div>
        );
    };

    return (
        <div className="p-4 md:p-6 max-w-[1600px] mx-auto h-auto md:h-[calc(100vh-2rem)] flex flex-col md:flex-row gap-6 pb-20">
            {/* Sidebar List */}
            <div className="w-full md:w-80 glass rounded-2xl overflow-hidden flex flex-col border border-white/40 shadow-xl shrink-0 h-64 md:h-auto">
                <div className="p-5 border-b border-white/20 bg-white/20 backdrop-blur-md space-y-4">
                    <h3 className="font-bold text-gray-800 flex items-center gap-2">
                        <i className="fas fa-folder-open text-purple-500"></i>
                        Artifacts
                    </h3>
                    {/* Search Bar */}
                    <div className="relative">
                        <i className="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-xs"></i>
                        <input 
                            type="text" 
                            placeholder="Filter reports..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full pl-8 pr-3 py-2 bg-white/50 border border-white/30 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                        />
                    </div>
                </div>
                
                <div className="overflow-y-auto flex-1 p-3 space-y-2 custom-scrollbar">
                    {filteredReports.map(r => {
                         const ext = r.path.split('.').pop().toLowerCase();
                         let icon = 'fa-file-alt text-gray-400';
                         let colorClass = 'bg-gray-100';
                         
                         if (['png', 'jpg', 'jpeg'].includes(ext)) { icon = 'fa-image text-pink-500'; colorClass = 'bg-pink-50'; }
                         if (ext === 'pdf') { icon = 'fa-file-pdf text-red-500'; colorClass = 'bg-red-50'; }
                         if (['md', 'txt'].includes(ext)) { icon = 'fa-file-alt text-blue-500'; colorClass = 'bg-blue-50'; }
                         
                         return (
                            <div key={r.id} onClick={() => setSelectedReport(r)} 
                                className={`p-3 rounded-xl cursor-pointer transition-all duration-200 group flex items-center gap-3 border
                                ${selectedReport?.id === r.id 
                                    ? 'bg-white border-purple-200 shadow-md ring-1 ring-purple-100' 
                                    : 'hover:bg-white/60 border-transparent hover:border-white/40 hover:shadow-sm'
                                }`}>
                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 transition-colors ${selectedReport?.id === r.id ? 'bg-purple-100' : colorClass}`}>
                                    <i className={`fas ${icon} text-lg ${selectedReport?.id === r.id ? '!text-purple-600' : ''}`}></i>
                                </div>
                                <div className="min-w-0 flex-1">
                                    <h4 className={`font-bold text-sm truncate ${selectedReport?.id === r.id ? 'text-purple-900' : 'text-gray-700'}`}>{r.title}</h4>
                                    <p className="text-xs mt-0.5 text-gray-400 truncate flex justify-between">
                                        <span>{r.date}</span>
                                        <span className="uppercase text-[10px] font-bold opacity-70 border px-1 rounded">{ext}</span>
                                    </p>
                                </div>
                            </div>
                        )
                    })}

                    {reports.length === 0 && (
                        <div className="p-8 text-center text-gray-400 text-sm border-2 border-dashed border-gray-200/50 rounded-xl m-2">
                            No artifacts found.
                        </div>
                    )}
                </div>
            </div>
            
            {/* Main Content Area */}
            <div className="flex-1 glass rounded-2xl overflow-hidden flex flex-col border border-white/40 shadow-2xl relative bg-white/60 backdrop-blur-xl">
                {selectedReport && renderToolbar()}
                <div className="flex-1 overflow-hidden relative flex flex-col">
                    {renderContent()}
                </div>
            </div>
        </div>
    );
};

const DataExplorer = ({ config }) => {
    const [tree, setTree] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const [fileContent, setFileContent] = useState('');
    const [fileType, setFileType] = useState(''); // 'csv' or 'json'

    useEffect(() => {
        if (config?.githubRepo) {
            setLoading(true);
            DataService.fetchRepoTree(config.githubRepo).then(data => { setTree(data.tree || []); setLoading(false); });
        }
    }, [config]);

    const handleFileClick = async (file) => {
        if (file.path.endsWith('.csv')) {
            setSelectedFile(file);
            setFileType('csv');
            setFileContent(await DataService.fetchFileContent(config.githubRepo, file.path));
        } else if (file.path.endsWith('.json')) {
            setSelectedFile(file);
            setFileType('json');
            setFileContent(await DataService.fetchFileContent(config.githubRepo, file.path));
        } else {
            window.open(`https://github.com/${config.githubRepo}/blob/main/${file.path}`, '_blank');
        }
    }

    const tableData = useMemo(() => {
        if (!fileContent) return { headers: [], rows: [], totalRows: 0 };

        let headers = [];
        let rows = [];

        if (fileType === 'csv') {
            const lines = fileContent.split('\n').filter(l => l.trim());
            if (lines.length) {
                headers = lines[0].split(',');
                rows = lines.slice(1).map(l => l.split(','));
            }
        } else if (fileType === 'json') {
            try {
                const json = JSON.parse(fileContent);
                let dataArray = [];
                if (Array.isArray(json)) dataArray = json;
                else if (typeof json === 'object' && json !== null) {
                    const possibleArray = Object.values(json).find(val => Array.isArray(val));
                    dataArray = possibleArray || [json];
                }
                
                if (dataArray.length) {
                    headers = Array.from(new Set(dataArray.flatMap(Object.keys)));
                    rows = dataArray.map(obj => headers.map(h => {
                         const val = obj[h];
                         return typeof val === 'object' ? JSON.stringify(val) : val;
                    }));
                } else {
                    headers = ['Info'];
                    rows = [['No tabular data found']];
                }
            } catch (e) {
                headers = ['Error'];
                rows = [['Invalid JSON content']];
            }
        }

        return { headers, rows: rows.slice(0, 50), totalRows: rows.length };
    }, [fileContent, fileType]);

    const handleShowMore = () => {
        const url = config.contactLink || `https://github.com/${config.githubRepo}`;
        window.open(url, '_blank');
    };

    return (
        <div className="p-8 max-w-7xl mx-auto h-auto md:h-[90vh] flex flex-col md:flex-row gap-6 pb-20">
            <div className="w-full md:w-1/3 glass rounded-2xl overflow-hidden flex flex-col border border-white/40 shadow-xl h-64 md:h-auto">
                <div className="p-5 border-b border-white/20 bg-white/20 backdrop-blur-md">
                    <h3 className="font-bold text-gray-800 flex items-center gap-2">
                        <i className="fas fa-database text-blue-500"></i>
                        Data Sources
                    </h3>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
                    {loading ? (
                        <div className="p-8 text-center text-gray-500">
                            <i className="fas fa-circle-notch fa-spin mb-2"></i><br/>Loading repository...
                        </div>
                    ) : tree.filter(i => i.path.startsWith('data/') || i.path.endsWith('.csv') || i.path.endsWith('.json')).map(item => (
                        <div 
                            key={item.path} 
                            onClick={() => handleFileClick(item)} 
                            className={`flex items-center gap-3 p-3 rounded-xl cursor-pointer text-sm transition-all duration-200 group
                                ${selectedFile?.path === item.path 
                                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-md' 
                                    : 'hover:bg-white/60 text-gray-600 hover:translate-x-1'
                                }`}
                        >
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 
                                ${selectedFile?.path === item.path ? 'bg-white/20' : 'bg-white/50'}`}>
                                <i className={`fas 
                                    ${item.path.endsWith('.csv') ? 'fa-table text-emerald-500' : ''} 
                                    ${item.path.endsWith('.json') ? 'fa-code text-amber-500' : ''}
                                    ${!item.path.endsWith('.csv') && !item.path.endsWith('.json') ? 'fa-folder text-blue-300' : ''}
                                    ${selectedFile?.path === item.path ? '!text-white' : ''}
                                `}></i>
                            </div>
                            <span className="truncate font-medium">{item.path}</span>
                        </div>
                    ))}
                </div>
            </div>
            
            <div className="flex-1 glass rounded-2xl overflow-hidden flex flex-col border border-white/40 shadow-xl relative bg-white/40">
                {selectedFile ? (
                    <>
                        <div className="p-4 border-b border-white/20 bg-gray-50/50 flex justify-between items-center">
                            <div className="flex items-center gap-2">
                                <i className={`fas ${fileType === 'csv' ? 'fa-table text-emerald-500' : 'fa-code text-amber-500'}`}></i>
                                <span className="font-bold text-gray-700">{selectedFile.path}</span>
                            </div>
                            <div className="flex items-center gap-3">
                                <span className="text-xs font-mono text-gray-500 bg-white px-2 py-1 rounded border">
                                    Showing {tableData.rows.length} of {tableData.totalRows} rows
                                </span>
                            </div>
                        </div>
                        <div className="overflow-auto flex-1 custom-scrollbar relative">
                            <table className="min-w-full text-sm text-left border-collapse">
                                <thead className="bg-gray-50 sticky top-0 z-10 shadow-sm">
                                    <tr>
                                        {tableData.headers?.map((h, i) => (
                                            <th key={i} className="px-6 py-3 font-semibold text-gray-600 uppercase tracking-wider text-xs border-b border-gray-200 bg-gray-50/95 backdrop-blur">
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100 bg-white/30">
                                    {tableData.rows?.map((r, i) => (
                                        <tr key={i} className="hover:bg-blue-50/50 transition-colors">
                                            {r.map((c, j) => (
                                                <td key={j} className="px-6 py-3 text-gray-600 border-b border-gray-100/50 max-w-xs truncate" title={c}>
                                                    {c}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            
                            {tableData.totalRows > 50 && (
                                <div className="sticky bottom-0 left-0 w-full bg-gradient-to-t from-white via-white/90 to-transparent p-8 flex justify-center z-20">
                                    <button 
                                        onClick={handleShowMore}
                                        className="bg-gray-900 text-white px-8 py-3 rounded-full font-bold shadow-lg hover:bg-gray-800 transition-all hover:scale-105 active:scale-95 flex items-center gap-2"
                                    >
                                        <i className="fas fa-external-link-alt"></i>
                                        Show More Data
                                    </button>
                                </div>
                            )}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
                        <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                            <i className="fas fa-search text-4xl text-gray-300"></i>
                        </div>
                        <p className="font-medium">Select a file to preview</p>
                        <p className="text-sm opacity-70">Supports CSV and JSON</p>
                    </div>
                )}
            </div>
        </div>
    );
};

const App = () => {
    const [config, setConfig] = useState(null);
    const [commits, setCommits] = useState([]);
    const [activeTab, setActiveTab] = useState('dashboard');
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

    useEffect(() => {
        DataService.loadConfig().then(data => {
            if (data) {
                setConfig(data);
                if (data.config?.githubRepo) DataService.fetchCommits(data.config.githubRepo).then(setCommits);
            }
        });
    }, []);

    if (!config) return <div className="flex items-center justify-center h-screen"><i className="fas fa-circle-notch fa-spin text-blue-400 text-3xl"></i></div>;

    const renderContent = () => {
        switch (activeTab) {
            case 'dashboard': return <Dashboard config={config} commits={commits} />;
            case 'reports': return <ReportsViewer />;
            case 'data': return <DataExplorer config={config.config} />;
            default: return <Dashboard config={config} />;
        }
    };

    return (
        <div className="flex min-h-screen">
            {/* Mobile Backdrop */}
            {mobileMenuOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden backdrop-blur-sm transition-opacity"
                    onClick={() => setMobileMenuOpen(false)}
                ></div>
            )}

            <Sidebar
                activeTab={activeTab}
                setActiveTab={(tab) => { setActiveTab(tab); setMobileMenuOpen(false); }}
                isCollapsed={sidebarCollapsed}
                setCollapsed={setSidebarCollapsed}
                mobileOpen={mobileMenuOpen}
                closeMobileMenu={() => setMobileMenuOpen(false)}
            />

            <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden relative">
                <div className="absolute top-0 left-0 w-full h-full overflow-hidden pointer-events-none -z-10">
                    <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-purple-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob"></div>
                    <div className="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-300 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-blob animation-delay-2000"></div>
                </div>

                <MobileHeader onMenuClick={() => setMobileMenuOpen(!mobileMenuOpen)} />

                <main className="flex-1 overflow-y-auto custom-scrollbar p-0 relative z-10 flex flex-col">
                    <div className="flex-1">
                        {renderContent()}
                    </div>
                    <Footer />
                </main>
            </div>
        </div>
    );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
