# Security Policy (SECURITY.md)

Security and user privacy are top priorities for **ReVox**.

## Supported Versions

| Version | Supported |
|---|---|
| 1.x (current) | :white_check_mark: |
| < 1.0 | :x: |

---

## 🔒 Safe Handling of Tokens and Credentials

- **Never share your `DISCORD_TOKEN`:** Your Discord bot token grants full control over your bot application in Discord.
- The `.env` file is explicitly ignored from Git tracking via `.gitignore`. If you ever accidentally commit or leak a token, navigate immediately to the [Discord Developer Portal](https://discord.com/developers/applications) and click **Reset Token**.
- ReVox only communicates locally on your machine (`127.0.0.1` / `localhost`). The web API (`5050`) and VoiceStudio connection (`3900`) operate strictly on the loopback interface and should not be exposed to the public Internet without secure reverse proxies or authenticated tunnels.

---

## 🚨 Reporting a Vulnerability

If you discover a security flaw or vulnerability:

1. **DO NOT open a public Issue** disclosing the vulnerability.
2. Report it privately via the **Security Advisories** tab on the GitHub repository or contact the project maintainer directly.
3. Include reproducible steps and an environment description if possible.

We are committed to reviewing and addressing any security reports promptly before releasing public patches.
