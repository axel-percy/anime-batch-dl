# 🎬 Anime Batch Downloader

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-red.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A powerful, modern web application that allows you to search, select, and batch download entire anime seasons from multiple sources. Download episodes in bulk, get them in organized ZIP files, and enjoy features like multi-threading, automatic language fallback, and beautiful progress tracking.

![Anime Batch Downloader Demo](https://via.placeholder.com/800x400?text=Anime+Batch+Downloader+Screenshot)

## ✨ Features

### 🚀 Core Functionality
- **Batch Downloading** - Download multiple episodes at once and get them in a single ZIP file
- **Multi-Source Support** - Choose from AnimePahe (kwik links) and AniKai (megaup.cc links)
- **Smart Language Fallback** - Automatically switches to SUB if DUB is not available
- **Multi-Threaded Downloads** - Configurable concurrent downloads for maximum speed
- **Cloudflare Bypass** - Successfully bypasses Cloudflare protection using advanced techniques

### 🎯 User Experience
- **Beautiful Dark Mode UI** - Modern, responsive interface that's easy on the eyes
- **Real-Time Progress Tracking** - Watch your downloads progress with detailed status updates
- **Organized File Structure** - Each anime gets its own folder: `Downloads/Anime/Anime-Name/`
- **Episode Renaming** - Files are automatically renamed to `Episode_001.mp4`, `Episode_002.mp4`, etc.
- **Search with Autocomplete** - Find any anime quickly with the intelligent search bar

### ⚙️ Advanced Features
- **Configurable Settings** - Choose quality (1080p, 720p, 480p, 360p), language, and download location
- **IDM Integration** - Option to use external downloaders like IDM
- **Retry on Failure** - Automatically retries failed downloads up to 3 times
- **Terminal Progress Bars** - Beautiful Rich library progress display in console
- **Random User Agents** - Avoids blocking by rotating user agents
