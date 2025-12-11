# 🔄 The Life Cycle of Your Dashboard

## 1. How is it "Kept Alive"?
**Good news:** You don't need to "keep it alive."
- This is a **Static Website**. It consists of just HTML, CSS, and JS files.
- **GitHub Pages** (or your Web Server) just serves these files to visitors.
- Unlike a Python/Node.js app, there is no process that can crash. If the server is on, your site is on.

## 2. How to Update Without Breaking
The fear of "breaking" comes from pushing bad code. Follow this **Safe Workflow**:

### Step 1: Make Changes Locally
- **Content**: Edit `docs/data.json` (add notes, change progress).
- **Code**: Edit `docs/app.js` (change UI logic).

### Step 2: Test Locally (The Safety Net) 🛡️
Before you push, check it on your computer:
1. Run the sync script:
   ```bash
   python autoscripts/sync_dashboard.py
   ```
   *(This ensures your data.js is valid and matches your json)*
2. Open `docs/index.html` in your browser.
3. **Does it load?** If yes, it's safe to push. If no, fix it locally first!

### Step 3: Push to "Backend" 🚀
You are correct! Since we don't have a database server, **GitHub IS your backend**.
To "save" your changes to the live site, you must commit them:

```bash
git add .
git commit -m "Update progress to 50%"
git push
```

### Step 4: Automatic Deployment
Once you push:
1. **GitHub Action** wakes up.
2. It runs the sync script again (just to be safe/automated).
3. It bundles everything.
4. It updates the live site (via Pages or Octopus).

## Summary
- **Backend** = `docs/data.json` file.
- **Update** = `git push`.
- **Safety** = Run `python autoscripts/sync_dashboard.py` and check `index.html` **before** pushing.
