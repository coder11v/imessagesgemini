# iMessage Gemini Catchup

A sleek desktop application that generates AI-powered summaries of your iMessage group chats using Google's Gemini API. Perfect for catching up on group conversations without reading through hundreds of messages.

## ✨ Features

- **AI-Powered Summaries** - Uses Google Gemini to extract key points, decisions, and action items
- **Two Input Modes**:
  - **Database Mode**: Directly query your macOS Messages database
  - **Clipboard Mode**: Paste messages from Messages.app
- **Smart Formatting**:
  - Bullet-point summaries (6-12 key points)
  - "Who said what" section with speaker positions
  - Action items with assignees and deadlines
- **Modern UI** - Clean, dark-themed Pygame interface with smooth interactions
- **Scrollable Output** - Easy navigation through longer summaries
- **macOS Native** - Integrates seamlessly with Messages.app and system clipboard

## 📋 Requirements

- **macOS** (10.13+) - For Messages.app and database access
- **Python** 3.10 or higher
- **Google Gemini API key** - [Get one free](https://ai.google.dev/)

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/coder11v/imessagesgemini.git
cd imessagesgemini
```

### 2. Install Dependencies
```bash
pip install google-genai python-dateutil pygame
```

### 3. Set Up API Key
Export your Gemini API key as an environment variable:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

To make this permanent, add it to your shell profile (`~/.zshrc`, `~/.bash_profile`, etc.):
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
```

### 4. Grant Database Permissions (First Time Only)

macOS will prompt you for permission to access the Messages database. Grant access when prompted, or manually authorize in:
**System Preferences → Security & Privacy → Full Disk Access** - Add Terminal/Python

## 💻 Usage

### Launch the Application
```bash
python imessage_gemini_ui.py
```

### Workflow

#### **Database Mode** (Recommended)
1. Select **Database Mode** in the config screen
2. Enter the group chat name (e.g., "My Group Chat", "Squad", "Team Planning")
3. Adjust the message count slider (20-500 messages)
4. Click **Generate Catchup**
5. Read your summary with action items highlighted

#### **Clipboard Mode**
1. Open Messages.app and select the messages you want to summarize
2. Copy the selection (Command+C)
3. Select **Clipboard Mode** in the app
4. Click **Generate Catchup**

### Keyboard Shortcuts
- **Command+V** - Paste chat name from clipboard
- **Command+C** - Copy text from input
- **Command+X** - Cut text from input
- **Backspace** - Delete characters
- **Scroll** - Navigate through summaries

## 🎨 UI Guide

### Screens

**Splash Screen**
- Welcome introduction with feature overview
- "Get Started" button to begin

**Configuration Screen**
- **Group Chat Name** - Enter the name of your group chat (fuzzy matching supported)
- **Message Count** - Slider to select 20-500 messages
- **Mode Selection** - Choose between Database and Clipboard
- **Generate Catchup** - Submit for processing

**Loading Screen**
- Spinner animation while Gemini generates summary

**Summary Screen**
- Scrollable formatted output with bullet points, speaker roles, and action items
- **Retry** - Generate another summary
- **Back** - Return to configuration

**Error Screen**
- Clear error messages if something goes wrong
- **Retry** - Try again
- **Back** - Return to start

## ⚙️ Configuration

### Environment Variables

```bash
# Required
export GEMINI_API_KEY="your-api-key"

# Optional - defaults to gemini-2.5-flash
export GEMINI_MODEL="gemini-3-pro"  # or any other Gemini model

# Optional - if your Messages.db is in a non-standard location
# DEFAULT: ~/Library/Messages/chat.db
```

### Advanced: Custom Gemini Models

Edit the model in the app by setting:
```bash
export GEMINI_MODEL="gemini-2.5-flash"
```

Available models:
- `gemini-2.5-flash` (fast, recommended)
- `gemini-1.5-pro` (more powerful)
- `gemini-1.5-flash` (fast)

## 🔧 Troubleshooting

### "No chat found matching 'chat name'"
- Check the exact name of your group chat in Messages.app
- Try partial names - fuzzy matching is supported
- Ensure no typos

### "osascript failed" or permission errors
- Grant Full Disk Access to Terminal/Python in System Preferences
- System Preferences → Security & Privacy → Full Disk Access

### Gemini API errors
- Verify your API key is correct: `echo $GEMINI_API_KEY`
- Check you have API credits remaining at [Google AI Studio](https://ai.google.dev/)
- Ensure internet connection is active

### Text input not working
- Click inside the text input field to focus it
- Command+V should paste from clipboard
- If paste doesn't work, try typing the chat name directly

### Messages.app clipboard mode not working
- Ensure Messages.app is the active (frontmost) window
- Select messages with mouse, then press Enter in the app
- Try selecting a smaller range of messages first

## 📊 Output Format

The AI summary includes:

```
=== CATCH-UP SUMMARY ===

• Key decision made about project timeline
• Sarah proposed new meeting schedule
• Q4 budget approved with 15% increase
• Action items assigned for next sprint
...

Who Said What:
- Sarah: Advocated for earlier timeline
- Mike: Concerned about resource allocation
- Emma: Suggested parallel workstreams

Action Items:
□ Sarah - Prepare detailed timeline breakdown (by Friday)
□ Mike - Review budget allocation (by EOD Wednesday)
□ Emma - Schedule team sync meeting (by Monday)
```

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Windows/Linux support
- Additional export formats (PDF, JSON)
- Custom summary templates
- Chat history browser
- Keyboard shortcuts guide

## 📝 License

MIT License - feel free to use, modify, and distribute.

## 🙋 Support

- **Issues** - Found a bug? [Open an issue](https://github.com/yourusername/imessage-gemini-catchup/issues)
- **Discussions** - Have ideas? [Start a discussion](https://github.com/yourusername/imessage-gemini-catchup/discussions)
- **API Help** - [Gemini API Documentation](https://ai.google.dev/docs)

## 📌 Privacy & Security

- Messages are sent to Google's Gemini API for processing
- Your Messages.db is **never** uploaded - only queried locally
- Clipboard mode processes only the messages you explicitly select
- Consider your organization's data policies before using with work chats
- API key should be treated as sensitive - never commit to version control

## 🎯 Roadmap

- [ ] Windows/Linux support
- [ ] PDF export of summaries
- [ ] Conversation threading detection
- [ ] Sentiment analysis
- [ ] Multi-chat comparison
- [ ] Scheduled auto-summaries
- [ ] Dark mode toggle
- [ ] Custom Gemini prompts

## 🙌 Acknowledgments

Built with:
- [Pygame](https://www.pygame.org/) - UI framework
- [Google Gemini API](https://ai.google.dev/) - AI summarization
- [python-dateutil](https://dateutil.readthedocs.io/) - Date handling

---

**Happy catching up!** 💬✨
