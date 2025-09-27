# GitHub Secrets Setup for DigitalOcean Deployment

## Required GitHub Secrets

You need to add these secrets to your GitHub repository:

### 1. DO_SSH_PRIVATE_KEY
Copy your SSH private key content:
```
```

### 2. DO_SSH_USER
✅ **Confirmed username: `root`**

SSH access is working! Use this value for the GitHub secret:
```
root
```

## How to Add Secrets to GitHub

1. Go to your GitHub repository: `https://github.com/yangliu2/decision_data`
2. Click "Settings" tab
3. Click "Secrets and variables" → "Actions"
4. Click "New repository secret"
5. Add these secrets:
   - Name: `DO_SSH_PRIVATE_KEY`, Value: [paste the SSH private key above]
   - Name: `DO_SSH_USER`, Value: [the username that works from testing]

## Next Steps

After adding the secrets:
1. Push any changes to trigger the deployment
2. Check the "Actions" tab in GitHub to see deployment progress
3. The API will be available at `http://206.189.185.129:8000`

## Current Droplet Setup Needed

Make sure your droplet has:
1. Git installed
2. Python/conda environment set up
3. Poetry installed
4. Your repository cloned in `/opt/decision_data`, `~/decision_data`, or `/home/$USER/decision_data`