#!/bin/bash

###############################################################################
# GitHub Push Helper Script
# 
# This script helps you push your code to GitHub with the proper setup.
# 
# Usage:
#   ./push-to-github.sh <github-username> <repo-name>
#
# Example:
#   ./push-to-github.sh myusername conversation-knowledge-mining-solution
###############################################################################

set -e

GITHUB_USERNAME=${1:-""}
REPO_NAME=${2:-""}

if [ -z "$GITHUB_USERNAME" ] || [ -z "$REPO_NAME" ]; then
    echo "❌ Error: GitHub username and repository name are required"
    echo "Usage: $0 <github-username> <repo-name>"
    echo "Example: $0 myusername conversation-knowledge-mining-solution"
    exit 1
fi

echo "=================================================="
echo "GitHub Push Helper"
echo "=================================================="
echo ""
echo "Username: $GITHUB_USERNAME"
echo "Repository: $REPO_NAME"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    echo "✅ Git initialized"
fi

# Update CODEOWNERS if it exists
if [ -f ".github/CODEOWNERS" ]; then
    echo "📝 Updating CODEOWNERS with your username..."
    sed -i "s/YOUR_GITHUB_USERNAME/$GITHUB_USERNAME/g" .github/CODEOWNERS
    echo "✅ CODEOWNERS updated"
fi

# Update dependabot.yml
if [ -f ".github/dependabot.yml" ]; then
    echo "📝 Updating dependabot.yml with your username..."
    sed -i "s/YOUR_GITHUB_USERNAME/$GITHUB_USERNAME/g" .github/dependabot.yml
    echo "✅ Dependabot configuration updated"
fi

# Update GITHUB_SETUP.md
if [ -f "GITHUB_SETUP.md" ]; then
    echo "📝 Updating GITHUB_SETUP.md with your repository info..."
    sed -i "s/YOUR_USERNAME/$GITHUB_USERNAME/g" GITHUB_SETUP.md
    sed -i "s/YOUR_REPO_NAME/$REPO_NAME/g" GITHUB_SETUP.md
    echo "✅ Setup guide updated"
fi

# Check if remote already exists
if git remote | grep -q "origin"; then
    CURRENT_REMOTE=$(git remote get-url origin)
    echo ""
    echo "⚠️  Remote 'origin' already exists: $CURRENT_REMOTE"
    read -p "Do you want to update it? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git remote remove origin
        git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
        echo "✅ Remote updated"
    fi
else
    echo "🔗 Adding GitHub remote..."
    git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"
    echo "✅ Remote added"
fi

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "📌 Renaming branch to 'main'..."
    git branch -M main
    echo "✅ Branch renamed to main"
fi

# Stage all files
echo "📦 Staging files..."
git add .
echo "✅ Files staged"

# Show status
echo ""
echo "📊 Git Status:"
git status --short

# Commit
echo ""
read -p "Enter commit message (or press Enter for default): " COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="feat: Add GHAS and CI/CD configuration

- Added GitHub Actions workflows for CI/CD
- Added CodeQL security scanning
- Added Dependabot for dependency updates
- Added Azure deployment workflow
- Added comprehensive documentation"
fi

echo "💾 Creating commit..."
git commit -m "$COMMIT_MSG"
echo "✅ Commit created"

# Push
echo ""
echo "🚀 Ready to push to GitHub!"
echo ""
echo "Repository URL: https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo ""
read -p "Push to GitHub now? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Pushing to GitHub..."
    git push -u origin main
    echo ""
    echo "✅ Code pushed successfully!"
    echo ""
    echo "=================================================="
    echo "🎉 Next Steps:"
    echo "=================================================="
    echo ""
    echo "1. Go to your repository:"
    echo "   https://github.com/$GITHUB_USERNAME/$REPO_NAME"
    echo ""
    echo "2. Enable GitHub Advanced Security:"
    echo "   → Settings → Code security and analysis"
    echo "   → Enable: CodeQL, Dependabot, Secret Scanning"
    echo ""
    echo "3. Configure Azure credentials (see GITHUB_SETUP.md Step 4)"
    echo ""
    echo "4. View your workflows:"
    echo "   https://github.com/$GITHUB_USERNAME/$REPO_NAME/actions"
    echo ""
    echo "📚 For detailed instructions, read: GITHUB_SETUP.md"
else
    echo ""
    echo "⏸️  Push cancelled. To push later, run:"
    echo "   git push -u origin main"
fi

echo ""
echo "Done! 🎉"
