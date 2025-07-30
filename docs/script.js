// API Base URL
const API_BASE = 'https://osm-dynamic-api-0506da85fcea.herokuapp.com/api';
const GITHUB_API = 'https://api.github.com';
const username = "phaze7r";
const repo = "geospatial-tagging-thesis";

// Utility Functions
function showStatus(elementId, message, isSuccess = true) {
  const element = document.getElementById(elementId);
  element.textContent = message;
  element.className = `status-message ${isSuccess ? 'status-success' : 'status-error'}`;

  // Clear message after 3 seconds
  setTimeout(() => {
    element.textContent = '';
    element.className = 'status-message';
  }, 3000);
}

function setLoading(elementId, isLoading = true) {
  const element = document.getElementById(elementId);
  if (isLoading) {
    element.classList.add('loading');
  } else {
    element.classList.remove('loading');
  }
}

// Progress Functions
function loadProgress() {
  setLoading('progress-fill', true);

  fetch(`${API_BASE}/progress`)
    .then(res => res.json())
    .then(data => {
      const progressFill = document.getElementById('progress-fill');
      const progressValue = document.getElementById('progress-value');

      // Animate progress bar
      setTimeout(() => {
        progressFill.style.width = data.value + '%';
        progressValue.textContent = data.value + '%';
      }, 300);

      setLoading('progress-fill', false);
    })
    .catch(() => {
      document.getElementById('progress-value').textContent = 'Error loading';
      setLoading('progress-fill', false);
    });
}

function updateProgress() {
  const value = document.getElementById('progress-input').value;
  const password = document.getElementById('progress-password').value;

  if (!value || !password) {
    showStatus('progress-update-msg', 'Please fill all fields', false);
    return;
  }

  if (value < 0 || value > 100) {
    showStatus('progress-update-msg', 'Progress must be between 0-100', false);
    return;
  }

  fetch(`${API_BASE}/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: parseInt(value), password })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showStatus('progress-update-msg', 'Updated successfully!', true);
        loadProgress();
        document.getElementById('progress-input').value = '';
        document.getElementById('progress-password').value = '';
      } else {
        showStatus('progress-update-msg', data.error || 'Update failed!', false);
      }
    })
    .catch(() => {
      showStatus('progress-update-msg', 'Network error', false);
    });
}

// Current Task Functions
function loadCurrentTask() {
  fetch(`${API_BASE}/current-task`)
    .then(res => res.json())
    .then(data => {
      document.getElementById('current-task').textContent = data.task || 'No current task set';
    })
    .catch(() => {
      document.getElementById('current-task').textContent = 'Unable to load current task';
    });
}

// Notes Functions
function loadNotes() {
  setLoading('notes-text', true);

  fetch(`${API_BASE}/notes`)
    .then(res => res.json())
    .then(data => {
      const notesElement = document.getElementById('notes-text');
      notesElement.textContent = data.text || 'No notes yet.';
      setLoading('notes-text', false);
    })
    .catch(() => {
      document.getElementById('notes-text').textContent = 'Unable to load notes';
      setLoading('notes-text', false);
    });
}

function updateNotes() {
  const text = document.getElementById('notes-input').value;
  const password = document.getElementById('notes-password').value;

  if (!text || !password) {
    showStatus('notes-update-msg', 'Please fill all fields', false);
    return;
  }

  fetch(`${API_BASE}/notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, password })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        showStatus('notes-update-msg', 'Updated successfully!', true);
        loadNotes();
        document.getElementById('notes-input').value = '';
        document.getElementById('notes-password').value = '';
      } else {
        showStatus('notes-update-msg', data.error || 'Update failed!', false);
      }
    })
    .catch(() => {
      showStatus('notes-update-msg', 'Network error', false);
    });
}

// Repository Activity Functions
function loadRepoActivity() {
  setLoading('repo-activity-box', true);

  fetch(`${API_BASE}/repo-activity`)
    .then(res => res.json())
    .then(commits => {
      let html = '';
      if (Array.isArray(commits) && commits.length > 0) {
        commits.slice(0, 10).forEach(commit => {
          const date = new Date(commit.commit.author.date);
          const timeAgo = getTimeAgo(date);

          html += `
            <div class="commit-item">
              <a href="${commit.html_url}" target="_blank" class="commit-link">
                ${commit.commit.message}
              </a>
              <div class="commit-meta">
                by ${commit.commit.author.name} • ${timeAgo}
              </div>
            </div>
          `;
        });
      } else {
        html = '<div style="color: #6c757d; text-align: center; padding: 2rem;">No recent activity found.</div>';
      }

      document.getElementById('repo-activity-box').innerHTML = html;
      setLoading('repo-activity-box', false);
    })
    .catch(() => {
      document.getElementById('repo-activity-box').innerHTML =
        '<div style="color: #dc3545; text-align: center; padding: 2rem;">Unable to load repository activity.</div>';
      setLoading('repo-activity-box', false);
    });
}

// Repository Info Functions
function loadRepoInfo() {
  fetch(`${GITHUB_API}/repos/${username}/${repo}`)
    .then(res => res.json())
    .then(data => {
      document.getElementById('repo-name').textContent = data.name;
      document.getElementById('repo-desc').textContent = data.description || 'No description available';
      document.getElementById('stars-count').textContent = data.stargazers_count;
      document.getElementById('forks-count').textContent = data.forks_count;
      document.getElementById('updated-date').textContent = new Date(data.updated_at).toLocaleDateString();
    })
    .catch(() => {
      document.getElementById('repo-name').textContent = 'Error loading repository';
    });
}

function loadCommits() {
  fetch(`${GITHUB_API}/repos/${username}/${repo}/commits?per_page=5`)
    .then(res => res.json())
    .then(data => {
      const commitsList = document.getElementById('commits');
      commitsList.innerHTML = data.map(commit => {
        const date = new Date(commit.commit.author.date);
        const timeAgo = getTimeAgo(date);

        return `
          <li>
            <div class="commit-message">${commit.commit.message}</div>
            <div class="commit-details">
              ${commit.commit.author.name} • ${timeAgo}
            </div>
          </li>
        `;
      }).join('');
    })
    .catch(() => {
      document.getElementById('commits').innerHTML =
        '<li style="color: #dc3545;">Unable to load commits</li>';
    });
}

// Activity Heatmap Functions
function loadActivityHeatmap() {
  fetch(`${GITHUB_API}/repos/${username}/${repo}/commits?per_page=100`)
    .then(res => res.json())
    .then(commits => {
      const activity = Array.from({length: 10}, () => Array(24).fill(0));
      const now = new Date();

      commits.forEach(commit => {
        const date = new Date(commit.commit.author.date);
        const diffDays = Math.floor((now - date) / (1000*60*60*24));
        if (diffDays < 10) {
          const hour = date.getHours();
          activity[9 - diffDays][hour] += 1;
        }
      });

      renderHeatmap(activity);
    })
    .catch(() => {
      document.getElementById('activity-heatmap').innerHTML =
        '<div style="color: #dc3545;">Unable to load activity data</div>';
    });
}

function renderHeatmap(activity) {
  const container = document.getElementById('activity-heatmap');
  container.innerHTML = '';

  for (let day = 0; day < 10; day++) {
    for (let hour = 0; hour < 24; hour++) {
      const cell = document.createElement('div');
      const commitCount = activity[day][hour];

      cell.className = 'activity-cell' + (commitCount > 0 ? ' active' : '');
      cell.title = `Day ${10-day}, Hour ${hour}: ${commitCount} commits`;
      cell.style.opacity = commitCount > 0 ? Math.min(1, commitCount / 3) : 0.3;

      container.appendChild(cell);
    }
  }
}

// Utility Functions
function getTimeAgo(date) {
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 60) return `${diffMins} minutes ago`;
  if (diffHours < 24) return `${diffHours} hours ago`;
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString();
}

// Initialize everything when page loads
document.addEventListener('DOMContentLoaded', function() {
  loadProgress();
  loadCurrentTask();
  loadNotes();
  loadRepoActivity();
  loadRepoInfo();
  loadCommits();
  loadActivityHeatmap();

  // Refresh data every 5 minutes
  setInterval(() => {
    loadProgress();
    loadCurrentTask();
    loadNotes();
    loadRepoActivity();
  }, 300000);
});