# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Eleanor, please report it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security vulnerabilities through one of these channels:

1. **GitHub Security Advisories** (Preferred)
   - Go to [Security Advisories](https://github.com/Project-Eleanor/Eleanor/security/advisories/new)
   - Create a new private security advisory

2. **Email**
   - Send details to: security@project-eleanor.io
   - Use our PGP key for sensitive information (available on our website)

### What to Include

Please include as much of the following information as possible:

- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of affected source files
- Location of the affected code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce
- Proof-of-concept or exploit code (if possible)
- Impact assessment

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Target**: Within 90 days (depending on complexity)

### What to Expect

1. **Acknowledgment**: We'll confirm receipt of your report
2. **Assessment**: We'll investigate and determine severity
3. **Updates**: We'll keep you informed of our progress
4. **Fix**: We'll develop and test a fix
5. **Disclosure**: We'll coordinate disclosure timing with you
6. **Credit**: We'll credit you in our security advisory (unless you prefer anonymity)

## Security Best Practices for Deployment

### Authentication

- Always use strong passwords (minimum 12 characters)
- Enable MFA where available
- Rotate API keys regularly
- Use LDAP/AD integration in production

### Network Security

- Deploy behind a reverse proxy (nginx, Traefik)
- Use TLS 1.3 for all connections
- Implement proper firewall rules
- Use network segmentation for sensitive components

### Data Protection

- Encrypt data at rest (Elasticsearch, PostgreSQL)
- Use secure backup procedures
- Implement proper access controls
- Follow data retention policies

### Container Security

- Use official images only
- Keep images updated
- Run containers as non-root
- Implement resource limits
- Use read-only file systems where possible

## Security Features

Eleanor includes several security features:

- **Audit Logging**: All actions are logged with user attribution
- **Role-Based Access Control**: Granular permissions system
- **Evidence Integrity**: SHA-256 hashing for chain of custody
- **Session Management**: Secure session handling with timeouts
- **Input Validation**: Comprehensive input sanitization

## Acknowledgments

We appreciate the security research community. Contributors who report valid security vulnerabilities will be acknowledged in our security advisories and CONTRIBUTORS file.

Thank you for helping keep Eleanor and its users safe!
