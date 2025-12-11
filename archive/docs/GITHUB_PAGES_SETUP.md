# 🌍 hosting on GitHub Pages

Since we are using the `docs/` folder for our dashboard, setting up GitHub Pages is extremely simple.

## 1. Enable GitHub Pages
1. Go to your GitHub Repository URL.
2. Click on **Settings** (top right tab).
3. On the left sidebar, click **Pages**.
4. Under **Build and deployment** > **Source**, assume "Deploy from a branch".
5. Under **Branch**, select:
   - Branch: `main` (or master)
   - Folder: `/docs` (This is important! Do not select /root).
6. Click **Save**.

## 2. Verify Deployment
- After a minute or two, refresh the page.
- You will see a banner saying "Your site is live at..."
- Click that link to see your dashboard!

## 🔄 How Usage Works
- **Update Content**: Edit `docs/data.json` locally or via the Admin interface (and download/commit it).
- **Push**: `git push origin main`.
- **Auto-Sync**: The GitHub Action I created (`update_dashboard.yml`) will automatically run, bundle your data into `data.js`, and commit it.
- **Deploy**: GitHub Pages will pick up the change and deploy the site automatically.
