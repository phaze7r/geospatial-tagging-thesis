# 🐙 Full Walkthrough: Connecting to Octopus Deploy

This guide will help you connect this GitHub repository to your Octopus Deploy instance so that every time you update your dashboard, it automatically deploys.

## ⚠️ Important Concept
**Octopus Deploy is a Delivery Pipeline**, not a hosting provider.
- It takes your code from GitHub.
- It "deploys" it to a server you own (e.g., an Azure Web App, an AWS EC2 instance, or a virtual machine).
- If you do not have a server, Octopus has nowhere to put your file!

---

## Phase 1: Connect GitHub to Octopus (The Handshake)

We need to give GitHub permission to talk to your Octopus server.

### 1. Get your Octopus API Key
1. Log in to **[Octopus Cloud](https://octopus.app/)**.
2. Click your **Profile Picture** (top right) → **Profile**.
3. Select the **My API Keys** tab.
4. Click **New API Key**.
   - Purpose: `GitHub Actions`
   - Click **Generate**.
5. **COPY THIS KEY**. You won't see it again.

### 2. Add Secrets to GitHub
1. Go to your GitHub Repository page.
2. Click **Settings** (top tab).
3. On the left, click **Secrets and variables** → **Actions**.
4. Click **New repository secret**.
   - **Name**: `OCTOPUS_SERVER_URL`
   - **Value**: Your Instance URL (e.g., `https://phaze7r.octopus.app`)
5. Click **New repository secret** again.
   - **Name**: `OCTOPUS_API_KEY`
   - **Value**: The API Key you copied in Step 1.

---

## Phase 2: Configure Octopus Deploy (The Coordinator)

Now we need to tell Octopus what to do with the files GitHub sends it.

### 1. Create an Environment
An "Environment" is just a label for where you are deploying (e.g., Production).
1. In Octopus, go to **Infrastructure** → **Environments**.
2. Click **Add Environment**.
3. Name it: `Production`
4. Click **Save**.

### 2. Create the Project
1. Go to **Projects**.
2. Click **Add Project**.
3. Name it: `Geospatial Dashboard`.
4. Click **Save**.

### 3. Define the Deployment Process
1. Inside your new Project, click **Process** (left sidebar).
2. Click **Add Step**.
3. **Choose your Target**:
   - *Scenario A: You have an Azure Web App* -> Search for "Deploy an Azure Web App".
   - *Scenario B: You have a Linux/Windows Server* -> Search for "Deploy to IIS" or "Transfer a Package".
   - *Scenario C: Just testing* -> Search for "Run a Script" (this will just run "Hello World" to prove it works).
4. For this walkthrough, let's assume you want to **Deploy to an Azure Web App**:
   - Select **Deploy an Azure Web App**.
   - **On Behalf Of**: Configure your Azure Account.
   - **Package Feed**: Select `Octopus Server (built-in)`.
   - **Package ID**: Type `dashboard-site` (This matches what we set in GitHub!).
5. Click **Save**.

---

## Phase 3: The Deployment Target (The Destination)

**This is the step most people miss.** You need a computer for Octopus to talk to.

1. Go to **Infrastructure** → **Deployment Targets**.
2. Click **Add Deployment Target**.
3. Choose your infrastructure (e.g., **Azure Web App** or **Listening Tentacle**).
4. Follow the wizard to connect your actual server.
5. **CRITICAL**: In the **Environments** field, select `Production`.
6. **CRITICAL**: In the **Roles** field, give it a tag (e.g., `web-server`). Ensure your Process step (Phase 2) targets this same Role.

---

## Phase 4: Test It!

1. Make a small change to your `docs/data.json` or `README.md`.
2. Push to GitHub: `git push`.
3. Watch the **Actions** tab in GitHub. You should see "Update Dashboard & Deploy".
4. Once green, go to **Octopus Deploy**. You should see a new Release created and deployed to Production!

✅ **Done!** Your pipeline is fully automated.
