#!/bin/bash

# Ensure a branch name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <branch-name>"
    exit 1
fi

TARGET_BRANCH=$1

# Restore all modifications (discard local changes)
echo "Restoring all modifications..."
git reset --hard HEAD
git clean -fd

# Fetch updates from the remote
echo "Fetching updates from remote..."
git fetch --all --prune

# Update all local branches to match remote
echo "Updating local branches with remote..."
for branch in $(git branch | sed 's/\*//g' | awk '{print $1}'); do
    git checkout $branch
    git reset --hard origin/$branch 2>/dev/null || echo "No remote tracking for $branch, skipping..."
done

# Checkout into the target branch
echo "Checking out into $TARGET_BRANCH..."
git checkout $TARGET_BRANCH || { echo "Branch $TARGET_BRANCH does not exist!"; exit 1; }

echo "Done."
