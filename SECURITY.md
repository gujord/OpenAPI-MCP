# Security Policy

## Supported Versions

We are committed to maintaining security for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## 🔒 Security Updates

### h11 Chunked-Encoding Vulnerability (Fixed - January 2025)

**Issue:** Previous versions used h11 < 0.15.0, which had a leniency in parsing line terminators in chunked-coding message bodies that could lead to request smuggling vulnerabilities.

**Solution:** Updated to h11 >= 0.16.0 and httpcore >= 1.0.9

**Impact:** High - Request smuggling attacks were possible when using vulnerable reverse proxies

**Fixed by:**
```bash
# Before (vulnerable)
h11<0.15,>=0.13
httpcore==1.0.7

# After (secure)  
h11>=0.16.0
httpcore>=1.0.9
```

**Verify fix:**
```bash
pip install -r requirements.txt --upgrade
python -c "import h11; print(f'h11 version: {h11.__version__}')"
# Should show: h11 version: 0.16.0 or higher
```

## Reporting a Vulnerability

If you discover a security issue:

1. **DO NOT** open a public issue for sensitive vulnerabilities
2. Open a [GitHub Issue](https://github.com/gujord/OpenAPI-MCP/issues) for non-sensitive issues
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and provide updates until resolved.

## Security Best Practices

### Production Deployment
- ✅ Always use the latest version
- ✅ Keep dependencies updated: `pip install -r requirements.txt --upgrade`
- ✅ Use HTTPS for all communications
- ✅ Implement proper authentication for APIs requiring it
- ✅ Monitor logs for suspicious activity

### Docker Security
- ✅ Use the official configuration (runs as non-root user)
- ✅ Keep Docker and base images updated
- ✅ Use Docker secrets for sensitive configuration

### Network Security
- ✅ Run behind a reverse proxy (nginx, cloudflare, etc.)
- ✅ Use firewalls to restrict access
- ✅ Implement rate limiting
- ✅ Use VPN/private networks when possible

## Security Checklist

Before deploying to production:

- [ ] Updated to latest version
- [ ] All dependencies updated
- [ ] Using HTTPS transport
- [ ] Proper authentication configured
- [ ] Reverse proxy configured
- [ ] Monitoring enabled
- [ ] Network access restricted

---

**Last updated: January 2025**
