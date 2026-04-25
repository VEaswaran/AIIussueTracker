# Jenkins Setup Guide — AI Issue Tracker MCP

---

## 0. Local vs Cloud — Which Should You Use?

### Option A — Run Jenkins Locally (Docker Desktop)
Best for: **development, testing, personal projects**

**Pros**
- Free, no account needed
- Up and running in 5 minutes
- Full control

**Cons**
- Only reachable from your machine (GitHub webhooks need a tunnel — see below)
- Stops when your laptop sleeps

#### Quick Start — Local Jenkins via Docker

```bash
# Pull and run Jenkins LTS
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  jenkins/jenkins:lts-jdk17
```

Then open **http://localhost:8080** — get the initial admin password:
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

> **Exposing localhost to GitHub webhooks (free):**
> Install [ngrok](https://ngrok.com/download) and run:
> ```bash
> ngrok http 8080
> ```
> Use the `https://xxxx.ngrok.io` URL as your GitHub webhook Payload URL.

---

### Option B — Jenkins on the Cloud
Best for: **team projects, always-on CI/CD, production**

| Provider | How | Cost |
|----------|-----|------|
| **AWS EC2** | Launch a `t3.small` (2 vCPU / 2 GB) Ubuntu instance, install Jenkins | ~$15/mo or Free Tier eligible |
| **Azure VM** | `B1ms` VM, install Jenkins | ~$15/mo |
| **GCP Compute Engine** | `e2-small`, install Jenkins | Free tier available |
| **CloudBees (SaaS Jenkins)** | Fully managed Jenkins — no install needed | Free tier available at [cloudbees.com](https://www.cloudbees.com) |
| **DigitalOcean Droplet** | 1-click Jenkins Droplet | $6/mo |

#### Quick Start — Cloud VM (Ubuntu)

```bash
# SSH into your VM, then:
sudo apt update && sudo apt install -y openjdk-17-jdk

# Add Jenkins repo
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key \
  | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] \
  https://pkg.jenkins.io/debian-stable binary/" \
  | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

sudo apt update && sudo apt install -y jenkins
sudo systemctl enable --now jenkins

# Get admin password
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Open `http://<your-vm-public-ip>:8080`

> **Security:** Open port `8080` in your VM's firewall / security group rules.
> For production, put Jenkins behind **nginx + HTTPS** with a domain name.

---

### ✅ Recommendation for You (Single Developer)

Since this is a **personal/dev project** right now:

```
Start LOCAL  →  graduate to Cloud when you need always-on builds
```

Use **Docker Desktop locally** + **ngrok** for webhooks — zero cost, works today.

---

## ⚡ When Does Each Check Trigger?

### Short answer:
> **A plain `git commit + push` to a branch does NOT trigger the GitHub Actions PR review.**
> You must open (or push to) a **Pull Request** targeting `main` or `develop`.

---

### Full trigger matrix

| Action | GitHub Actions PR Review | Jenkins Pipeline |
|--------|--------------------------|-----------------|
| `git push` to any branch | ❌ No | ✅ Yes (within 5 min via poll, or instant via webhook) |
| Open a new PR → `main` or `develop` | ✅ Yes (`opened`) | ✅ Yes |
| Push a new commit to an open PR | ✅ Yes (`synchronize`) | ✅ Yes |
| Reopen a closed PR | ✅ Yes (`reopened`) | ✅ Yes |
| Direct push to `main` (no PR) | 🚫 **Blocked by branch protection** | 🚫 **Fails at Guard stage** |
| Push to a feature branch (no PR yet) | ❌ No | ✅ Yes |

---

### So your typical workflow is:

```
1. git checkout -b feature/my-change
2. git commit -m "my change"
3. git push origin feature/my-change     ← Jenkins builds this immediately
4. Open a Pull Request on GitHub          ← GitHub Actions AI review triggers
5. Push more commits to the PR branch    ← Both Jenkins + GitHub Actions re-trigger
6. Merge PR into main                    ← Jenkins builds main + deploys (if configured)
```

---

## 1. Prerequisites

| Tool | Version |
|------|---------|
| Jenkins | 2.440+ (LTS recommended) |
| JDK | 17 (Eclipse Temurin) |
| Maven | 3.9+ |
| Git | any recent |

> 🐳 Docker not required — add when Docker stages are re-enabled.

---

## 2. Install Required Plugins

Go to **Jenkins → Manage Jenkins → Plugins → Available** and install everything in
[`required-plugins.txt`](required-plugins.txt).

---

## 3. Configure Global Tools

**Jenkins → Manage Jenkins → Global Tool Configuration**

| Tool | Name (must match Jenkinsfile) | Install automatically |
|------|-------------------------------|-----------------------|
| JDK  | `JDK-17` | ✅ Eclipse Temurin 17 |
| Maven | `Maven-3.9` | ✅ Apache Maven 3.9.x |

---

## 4. Add Credentials

**Jenkins → Manage Jenkins → Credentials → System → Global credentials**

| ID | Kind | What |
|----|------|------|
| `deploy-ssh-key` | SSH Username with private key | SSH key for deployment server |

> 🐳 **Docker credentials** (`docker-registry-creds`) — not needed yet. Add later when Docker push is enabled.

---

## 5. Configure Environment Variables (optional)

**Jenkins → Manage Jenkins → System → Global properties → Environment variables**

| Variable | Example | Purpose |
|----------|---------|---------|
| `DEPLOY_HOST` | `10.0.0.5` | SSH deploy target — leave blank to skip deploy |
| `DEPLOY_USER` | `ubuntu` | SSH user on deploy host |
| `DEPLOY_PATH` | `/opt/ai-issue-tracker` | Deploy directory on remote host |
| `SONAR_HOST_URL` | `http://sonar:9000` | SonarQube — leave blank to skip |
| `SONAR_TOKEN` | `squ_xxx` | SonarQube auth token |

> 🐳 `DOCKER_REGISTRY` removed — add back when Docker push is enabled.

---

## 6. Create the Pipeline Job

1. **New Item** → name it `ai-issue-tracker-mcp` → choose **Multibranch Pipeline**
2. **Branch Sources** → Add **GitHub**
   - Repository HTTPS URL: `https://github.com/<your-org>/AIIssueTracker`
   - Credentials: your GitHub credentials
3. **Build Configuration** → Mode: **by Jenkinsfile** → Script Path: `Jenkinsfile`
4. **Scan Multibranch Pipeline Triggers** → check **Periodically if not otherwise run** → 5 min
5. Save → **Scan Multibranch Pipeline Now**

---

## 7. GitHub Webhook (recommended — faster than polling)

In your GitHub repo → **Settings → Webhooks → Add webhook**

| Field | Value |
|-------|-------|
| Payload URL | `http://<jenkins-host>/github-webhook/` |
| Content type | `application/json` |
| Events | **Just the push event** + **Pull requests** |

---

## 7a. 🔒 Block Direct Pushes to `main` (Required)

This is enforced at **two levels** — both must be set up.

### Level 1 — GitHub Branch Protection Rule (hard block at repo level)

Go to your GitHub repo → **Settings → Branches → Add branch protection rule**

| Setting | Value |
|---------|-------|
| Branch name pattern | `main` |
| ✅ Require a pull request before merging | Enable |
| &nbsp;&nbsp;— Required approvals | `1` |
| &nbsp;&nbsp;— ✅ Require review from Code Owners | **Enable** — only CODEOWNERS can approve |
| &nbsp;&nbsp;— ✅ Dismiss stale PR approvals when new commits are pushed | Enable |
| ✅ Require status checks to pass before merging | Enable |
| &nbsp;&nbsp;— Required check | `AI Review (Jira disabled — no enterprise account)` |
| ✅ Do not allow bypassing the above settings | Enable |
| ✅ Restrict who can push to matching branches | Enable — CODEOWNERS only |
| ❌ Allow force pushes | **Leave OFF** |
| ❌ Allow deletions | **Leave OFF** |

> **CODEOWNERS** are defined in `.github/CODEOWNERS`. Edit that file to add/remove approvers.
> With "Require review from Code Owners" ON, **only the users listed in CODEOWNERS can approve and merge PRs** — including bot/agent merges which also go through this gate.

---

### Level 2 — Jenkins Guard Stage (catches anything that slips through)

The `Jenkinsfile` has a `Guard — No Direct Push to main` stage that checks `CHANGE_ID`:
- `CHANGE_ID` is **only set** when the build was triggered by a Pull Request
- If `CHANGE_ID` is missing on the `main` branch → build **immediately fails** with a clear message:

```
╔══════════════════════════════════════════════════════════════╗
║  ❌  DIRECT PUSH TO main IS NOT ALLOWED                      ║
║                                                              ║
║  Please open a Pull Request from your feature branch.        ║
║  Direct commits to main are rejected by CI policy.           ║
╚══════════════════════════════════════════════════════════════╝
```

---

### Protection Summary

```
Developer tries to push directly to main
         │
         ▼
  GitHub rejects it  ──────────────────────────────────► ❌ Blocked at GitHub (Level 1)
  (Branch Protection + CODEOWNERS)
         │ (if somehow bypassed)
         ▼
  Jenkins Guard Stage ─────────────────────────────────► ❌ Build fails immediately (Level 2)


Developer opens a PR
         │
         ▼
  GitHub Actions AI Review runs
         │
         ▼
  CODEOWNER reviews + approves PR ────────────────────► ✅ Only CODEOWNER can approve
         │
         ├─ Small PR + agent auto-merge?
         │       └─ Agent checks CODEOWNER approval ──► ✅ Auto-merges if approved
         │                                              ❌ Posts "waiting for CODEOWNER" if not
         │
         └─ Medium/Large PR
                 └─ CODEOWNER manually merges ─────────► ✅ Merges after approval
```

---

## 8. Pipeline Flow

```
Checkout
   │
   ▼
Build & Test  ──────────── (mvn clean verify, JUnit + JaCoCo reports)
   │
   ▼
Code Quality  ──────────── (SonarQube — skipped if SONAR_HOST_URL not set)
   │
   ▼
Package  ───────────────── (mvn package -DskipTests, archives fat JAR)
   │
   ▼  [main only, DEPLOY_HOST set]
Deploy        ──────────── (SCP JAR → SSH start.sh → health check)

🐳 Docker Build / Push stages removed — add back when registry is ready
```

---

## 9. Relationship with GitHub Actions

Both CI systems coexist and serve different purposes:

| | GitHub Actions (`.github/workflows/pr-review.yml`) | Jenkins (`Jenkinsfile`) |
|--|--|--|
| **Trigger** | Pull Request opened / updated | Push to any branch / PR |
| **Purpose** | AI-powered PR code review | Build, test, package, deploy |
| **What it runs** | Python agent + Copilot API | Maven build + SSH deploy |
| **Jira** | Disabled (commented out) | N/A |


