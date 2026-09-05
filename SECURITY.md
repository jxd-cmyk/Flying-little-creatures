\# Security Policy



\## Supported Versions



Only the latest version of Bug Dance on the main branch is currently supported for security updates.



| Version | Supported          |

| ------- | ------------------ |

| 1.0.x   | :white\_check\_mark: |

| < 1.0   | :x:                |



\---



\## Security Model \& Privacy Guarantees



Bug Dance is designed as a lightweight, offline Windows desktop utility. It adheres to strict security and privacy standards:



\* \*\*Zero Network Activity:\*\* The application operates completely offline. It does not send telemetry, analytics, crash logs, or external HTTP/HTTPS requests.

\* \*\*Non-Privileged Registry Access:\*\* Automatic startup features modify only the `HKEY\_CURRENT\_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run` registry hive. The application does not request or require elevated administrative (UAC) privileges.

\* \*\*Transparent Pass-Through Windows:\*\* Overlay widgets use native Windows transparency (`Qt.WindowTransparentForInput`), ensuring they do not capture keystrokes, steal screen focus, or block mouse interaction with underlying applications.

\* \*\*Local Asset Loading:\*\* All images (`Jaroslav.M.Soukup\_bugs\_\*.png`) and icon files are loaded strictly from the local executable directory.



\---



\## Reporting a Vulnerability



If you discover a security vulnerability or potential threat within Bug Dance, please report it directly to the maintainer rather than opening a public issue.



\### How to Report



\* \*\*Email:\*\* Send details of the issue to \[jxd@jxd.cz](mailto:jxd@jxd.cz).

\* \*\*Information to Include:\*\*

&#x20; \* Description of the vulnerability or security flaw.

&#x20; \* Steps to reproduce the issue.

&#x20; \* Windows OS build and Python environment version.

&#x20; \* Proof of Concept (PoC) code or demonstration (if applicable).



\### Response Timeline



\* \*\*Acknowledgment:\*\* Within 48 hours of receiving the email.

\* \*\*Assessment \& Fix:\*\* Security patches or updates will be addressed as promptly as possible based on severity.



\---



\*Software © Jiri X. Dolezal | JXD VibeLabs\*

