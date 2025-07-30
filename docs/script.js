// Fetch and display progress
function loadProgress() {
  fetch('https://osm-dynamic-api-0506da85fcea.herokuapp.com/api/progress')
    .then(res => res.json())
    .then(data => {
      document.getElementById('progress-bar').value = data.value;
      document.getElementById('progress-value').textContent = data.value + '%';
    });
}
loadProgress();

// Update progress (admin only)
function updateProgress() {
  const value = document.getElementById('progress-input').value;
  const password = document.getElementById('progress-password').value;
  fetch('https://osm-dynamic-api-0506da85fcea.herokuapp.com/api/progress', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value, password })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        document.getElementById('progress-update-msg').textContent = 'Updated!';
        loadProgress();
      } else {
        document.getElementById('progress-update-msg').textContent = data.error || 'Failed!';
      }
    });
}

// Fetch and display notes
function loadNotes() {
  fetch('https://osm-dynamic-api-0506da85fcea.herokuapp.com/api/notes')
    .then(res => res.json())
    .then(data => {
      document.getElementById('notes-text').textContent = data.text;
    });
}
loadNotes();

// Update notes (admin or supervisor)
function updateNotes() {
  const text = document.getElementById('notes-input').value;
  const password = document.getElementById('notes-password').value;
  fetch('https://osm-dynamic-api-0506da85fcea.herokuapp.com/api/notes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, password })
  })
    .then(res => res.json())
    .then(data => {
      if (data.success) {
        document.getElementById('notes-update-msg').textContent = 'Updated!';
        loadNotes();
      } else {
        document.getElementById('notes-update-msg').textContent = data.error || 'Failed!';
      }
    });
}

// Fetch and display repo activity
function loadRepoActivity() {
  fetch('https://osm-dynamic-api-0506da85fcea.herokuapp.com/api/repo-activity')
    .then(res => res.json())
    .then(commits => {
      let html = '';
      if (Array.isArray(commits)) {
        commits.forEach(commit => {
          html += `<div style="margin-bottom: 10px;">
            <a href="${commit.html_url}" target="_blank" style="color: #ff6600; text-decoration: underline;">
              ${commit.commit.message}
            </a>
            <div style="font-size: 0.9em; color: #aaa;">
              by ${commit.commit.author.name} at ${new Date(commit.commit.author.date).toLocaleString()}
            </div>
          </div>`;
        });
      } else {
        html = 'Unable to load activity.';
      }
      document.getElementById('repo-activity-box').innerHTML = html;
    });
}
loadRepoActivity();