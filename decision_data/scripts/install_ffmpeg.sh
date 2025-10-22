#!/bin/bash
# Install ffmpeg on Ubuntu server

echo "Updating package lists..."
apt-get update -qq

echo "Installing ffmpeg..."
DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg

echo "Verifying installation..."
ffmpeg -version | head -1

echo "Done!"
