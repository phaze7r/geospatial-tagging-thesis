# Frontend Modernization Walkthrough

I have completely revamped the `docs/index.html` to be a modern, React-based Single Page Application (SPA). This resolves the issue of being "unable to update" by introducing a local data source and a file-based update workflow suitable for GitHub Pages.

## 🚀 Enhancements

### 1. Modern Dashboard Architecture
- **Modular Code**: Split the monolithic HTML into `app.js` (Logic), `style.css` (Design), and `data.json` (Content).
- **Sidebar Navigation**: Dedicated sections for **Dashboard**, **Reports**, and **Data Explorer**.
- **Responsive Design**: Works seamlessly on mobile and desktop using Tailwind CSS.
- **Offline/Local Mode**: Works directly from your file system (`file://`) thanks to the bundled `data.js`.

### 2. "Admin Mode" & **AUTOMATED** Content Updates
- **Solution**: Dynamic content (Progress, Notes) is in `docs/data.json`.
- **How to Update**:
  1. Go to the **Login** tab as Admin (`admin` / `admin123`).
  2. Edit Progress/Notes -> **"Save Changes"** -> Overwrite `docs/data.json`.
  3. **Commit & Push**.
  4. **GitHub Action Magic**: I have set up a new workflow (`.github/workflows/update_dashboard.yml`). When you push `data.json`, it **automatically** updates `data.js` and commits it back to your repo.
  
  > You don't need to manually update `data.js` anymore. Just edit `data.json` and push. The site stays in sync automatically!

### 3. Reports Viewer
- Added a **Reports** tab that dynamically renders Markdown files.
- Works offline! Automagically bundled by the new GitHub Action.

## 📂 New File Structure
- `docs/index.html`: Lightweight entry point.
- `docs/app.js`: Main application logic.
- `docs/data.json`: Primary data source (Edit this!).
- `docs/data.js`: Auto-generated bundle (Don't touch!).
- `autoscripts/sync_dashboard.py`: The script that does the bundling.
