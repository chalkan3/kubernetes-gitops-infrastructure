# Repository Mirror Setup

This repository is automatically mirrored between GitHub and Gitea.

## Architecture

```
GitHub (Public)                    Gitea (Private VPN)
├── Main repository                ├── Origin repository
├── Public documentation           ├── Internal development
└── Community contributions        └── Production deployments
     │                                  │
     └──────── Bidirectional ──────────┘
               Sync via Actions
```

## Setup Instructions

### 1. GitHub to Gitea Mirror (Automated)

The repository includes a GitHub Action (`.github/workflows/mirror.yml`) that automatically mirrors commits from GitHub to Gitea.

**To enable:**

1. Generate a Gitea access token:
   - Log in to Gitea: https://git.keite-guica.chalkan3.com.br
   - Go to Settings → Applications → Generate New Token
   - Name: "GitHub Mirror Bot"
   - Scopes: `write:repository`
   - Copy the token

2. Add the token to GitHub Secrets:
   - Go to GitHub repository Settings
   - Navigate to Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GITEA_TOKEN`
   - Value: (paste the Gitea token)
   - Click "Add secret"

3. Test the workflow:
   ```bash
   # Make any commit and push to GitHub
   git add .
   git commit -m "Test mirror sync"
   git push github main

   # Or trigger manually from GitHub Actions UI
   ```

### 2. Local Development Setup

For local development, configure both remotes:

```bash
# Clone from GitHub
git clone https://github.com/chalkan3/kubernetes-gitops-infrastructure.git
cd kubernetes-gitops-infrastructure

# Add Gitea as additional remote
git remote add gitea https://git.keite-guica.chalkan3.com.br/chalkan3/helmfile-rabbitmq.git

# Verify remotes
git remote -v
```

### 3. Push to Both Remotes

#### Option A: Push to both manually
```bash
git push github main
git push gitea main
```

#### Option B: Configure push to both remotes
```bash
# Configure origin to push to both
git remote set-url --add --push origin https://github.com/chalkan3/kubernetes-gitops-infrastructure.git
git remote set-url --add --push origin https://git.keite-guica.chalkan3.com.br/chalkan3/helmfile-rabbitmq.git

# Now a single push updates both
git push origin main
```

#### Option C: Use a script
```bash
#!/bin/bash
# save as: push-all.sh

git push github main
git push gitea main

echo "✅ Pushed to all remotes"
```

## Mirror Workflow Details

The GitHub Action (`.github/workflows/mirror.yml`) runs on:
- Every push to `main` branch
- Manual trigger via GitHub UI

**What it does:**
1. Checks out the repository with full history
2. Configures git with bot credentials
3. Adds Gitea remote using secret token
4. Force pushes to Gitea to ensure sync

**Benefits:**
- ✅ Automatic synchronization
- ✅ Public repository on GitHub for visibility
- ✅ Private repository on Gitea for production
- ✅ No manual intervention required

## Troubleshooting

### Mirror workflow fails

**Check:**
1. Gitea token is valid and has write permissions
2. GitHub secret `GITEA_TOKEN` is correctly set
3. Gitea server is accessible from GitHub Actions runners

**Debug:**
```bash
# Test Gitea access locally
git ls-remote https://git.keite-guica.chalkan3.com.br/chalkan3/helmfile-rabbitmq.git
```

### Out of sync repositories

**Manually sync from GitHub to Gitea:**
```bash
git clone https://github.com/chalkan3/kubernetes-gitops-infrastructure.git temp-repo
cd temp-repo
git remote add gitea https://git.keite-guica.chalkan3.com.br/chalkan3/helmfile-rabbitmq.git
git push gitea main --force
cd ..
rm -rf temp-repo
```

**Manually sync from Gitea to GitHub:**
```bash
git clone https://git.keite-guica.chalkan3.com.br/chalkan3/helmfile-rabbitmq.git temp-repo
cd temp-repo
git remote add github https://github.com/chalkan3/kubernetes-gitops-infrastructure.git
git push github main --force
cd ..
rm -rf temp-repo
```

## Best Practices

1. **Primary Development**: Use GitHub for public contributions
2. **Production Deployments**: ArgoCD watches Gitea repository
3. **Documentation**: Keep README updated on GitHub
4. **Secrets**: Never commit secrets - use GitHub Secrets and Kubernetes Secrets
5. **Sync Check**: Occasionally verify both repositories are in sync

## Security Notes

- Gitea is on private VPN (10.8.0.6) accessible only via WireGuard
- GitHub is public for open-source visibility
- Sensitive data should never be committed to either repository
- Use ArgoCD Vault Plugin or Sealed Secrets for production secrets
